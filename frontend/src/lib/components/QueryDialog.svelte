<script lang="ts">
	import { currentProject, identifiedSections, generatedDiagrams, diagramCache } from '$lib/stores';
	import { generateSectionDiagram } from '$lib/api';
	import type { WikiSection } from '$lib/types';
	import FileTreeNode from './FileTreeNode.svelte';

	export let isOpen = false;
	export let onClose: () => void;

	let prompt = '';
	let selectedSectionId = '';
	let selectedDiagramType: 'flowchart' | 'sequence' | 'class' | 'stateDiagram' | 'erDiagram' = 'flowchart';
	let referenceMode: 'auto' | 'manual' = 'auto';
	let selectedFiles: string[] = [];
	let showFileSelector = false;
	let fileTree: any = null;
	let error = '';
	let generatingInBackground: Set<string> = new Set();
	let isGenerating = false;

	const diagramTypes = [
		{ value: 'flowchart', label: 'Flowchart', description: 'Process flows, system architecture' },
		{ value: 'sequence', label: 'Sequence Diagram', description: 'Interactions over time' },
		{ value: 'class', label: 'Class Diagram', description: 'Object-oriented structure' },
		{ value: 'stateDiagram', label: 'State Diagram', description: 'State transitions' },
		{ value: 'erDiagram', label: 'ER Diagram', description: 'Database relationships' }
	];

	async function loadFileTree() {
		if (!$currentProject || fileTree) return;
		
		try {
			const response = await fetch('http://localhost:8001/getFolderTree', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ root_path: $currentProject })
			});
			
			if (response.ok) {
				const data = await response.json();
				fileTree = data.tree;
			}
		} catch (err) {
			console.error('Failed to load file tree:', err);
		}
	}

	function toggleFileSelection(filePath: string) {
		if (selectedFiles.includes(filePath)) {
			selectedFiles = selectedFiles.filter(f => f !== filePath);
		} else {
			selectedFiles = [...selectedFiles, filePath];
		}
	}

	function collectFiles(node: any): string[] {
		if (!node) return [];
		if (node.type === 'file') return [node.path];
		if (node.type === 'folder' && node.children) {
			return node.children.flatMap(collectFiles);
		}
		return [];
	}

	$: if (referenceMode === 'manual' && !fileTree) {
		loadFileTree();
	}

	async function handleGenerate() {
		if (!prompt.trim() || !$currentProject) return;

		error = '';
		isGenerating = true;

		// Find the selected section or create new
		let section: WikiSection | undefined;
		
		if (selectedSectionId) {
			section = $identifiedSections.find(s => s.section_id === selectedSectionId);
		}
		
		if (!section) {
			// Create a custom section based on the prompt
			section = {
				section_id: `custom_${Date.now()}`,
				section_title: prompt,
				section_description: prompt,
				diagram_type: selectedDiagramType,
				key_concepts: []
			};
		} else {
			// Update the diagram type if user selected a different one
			section = {
				...section,
				diagram_type: selectedDiagramType
			};
		}

		const sectionToGenerate = section;
		const projectPath = $currentProject;
		
		// Mark as generating
		generatingInBackground.add(sectionToGenerate.section_id);
		generatingInBackground = generatingInBackground;
		
		// Generate and wait for completion
		try {
			const referenceFiles = referenceMode === 'manual' ? selectedFiles : undefined;
			const diagram = await generateSectionDiagram(projectPath, sectionToGenerate, referenceFiles);
			
			// Add to frontend cache
			diagramCache.update(cache => {
				const newCache = new Map(cache);
				newCache.set(sectionToGenerate.section_id, diagram);
				return newCache;
			});
			
			// Add the custom section to identifiedSections if it's new
			if (sectionToGenerate.section_id.startsWith('custom_')) {
				identifiedSections.update(sections => {
					if (!sections.some(s => s.section_id === sectionToGenerate.section_id)) {
						const updatedSection = {
							...sectionToGenerate,
							section_title: diagram.section_title || sectionToGenerate.section_title
						};
						return [...sections, updatedSection];
					}
					return sections;
				});
			}
			
			// Mark as generated
			generatedDiagrams.update(set => {
				const newSet = new Set(set);
				newSet.add(sectionToGenerate.section_id);
				return newSet;
			});
			
			// Open the diagram
			window.dispatchEvent(new CustomEvent('openDiagram', { detail: diagram }));
			
			// Close dialog after successful generation
			prompt = '';
			selectedSectionId = '';
			selectedDiagramType = 'flowchart';
			selectedFiles = [];
			referenceMode = 'auto';
			onClose();
		} catch (err) {
			console.error('Failed to generate diagram:', err);
			error = err instanceof Error ? err.message : 'Failed to generate diagram';
		} finally {
			generatingInBackground.delete(sectionToGenerate.section_id);
			generatingInBackground = generatingInBackground;
			isGenerating = false;
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			onClose();
		}
	}
</script>

<svelte:window on:keydown={handleKeydown} />

{#if isOpen}
	<!-- Floating dialog - bottom right corner, no blocking backdrop -->
	<div class="fixed bottom-6 right-6 bg-white rounded-lg shadow-2xl w-96 z-50 border border-gray-200">
		<!-- Loading Overlay -->
		{#if isGenerating}
			<div class="absolute inset-0 bg-white bg-opacity-90 backdrop-blur-sm rounded-lg z-10 flex flex-col items-center justify-center">
				<svg class="animate-spin h-12 w-12 text-blue-600 mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
				</svg>
				<p class="text-gray-700 font-medium">Generation in progress...</p>
				<p class="text-gray-500 text-sm mt-1">Please wait</p>
			</div>
		{/if}
		
		<!-- Header -->
		<div class="flex items-center justify-between p-4 border-b border-gray-200">
			<h2 class="text-lg font-semibold text-gray-900">Generate Custom Diagram</h2>
			<button
				on:click={onClose}
				class="p-1 hover:bg-gray-100 rounded transition-colors"
				title="Close"
			>
				<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
					<path
						fill-rule="evenodd"
						d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
						clip-rule="evenodd"
					/>
				</svg>
			</button>
		</div>

		<!-- Content -->
		<div class="p-4">
			<div class="space-y-3">
				<!-- Prompt Input -->
				<div>
					<label for="prompt" class="block text-xs font-medium text-gray-700 mb-1">
						What would you like to visualize?
					</label>
					<textarea
						id="prompt"
						bind:value={prompt}
						rows="3"
						placeholder="E.g., 'Show me the authentication flow'"
						class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
					></textarea>
				</div>

				<!-- Diagram Type Selector -->
				<div>
					<label for="diagramType" class="block text-xs font-medium text-gray-700 mb-1">
						Diagram Type
					</label>
					<select
						id="diagramType"
						bind:value={selectedDiagramType}
						class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
					>
						{#each diagramTypes as type}
							<option value={type.value}>
								{type.label} - {type.description}
							</option>
						{/each}
					</select>
				</div>

				<!-- Reference Mode Selector -->
				<div>
					<div class="block text-xs font-medium text-gray-700 mb-1">
						Reference Documents
					</div>
					<div class="flex gap-2">
						<button
							type="button"
							on:click={() => referenceMode = 'auto'}
							class="flex-1 px-3 py-2 text-sm rounded-md transition-colors {referenceMode === 'auto' 
								? 'bg-blue-600 text-white' 
								: 'bg-gray-100 text-gray-700 hover:bg-gray-200'}"
						>
							Auto (RAG)
						</button>
						<button
							type="button"
							on:click={() => { referenceMode = 'manual'; loadFileTree(); }}
							class="flex-1 px-3 py-2 text-sm rounded-md transition-colors {referenceMode === 'manual' 
								? 'bg-blue-600 text-white' 
								: 'bg-gray-100 text-gray-700 hover:bg-gray-200'}"
						>
							Manual
						</button>
					</div>
					{#if referenceMode === 'auto'}
						<p class="text-xs text-gray-500 mt-1">Backend will automatically retrieve relevant files</p>
					{:else}
						<p class="text-xs text-gray-500 mt-1">Select specific files to reference ({selectedFiles.length} selected)</p>
					{/if}
				</div>

				<!-- File Selector (Manual Mode) -->
				{#if referenceMode === 'manual'}
					<div class="border border-gray-300 rounded-md overflow-hidden">
						<div class="bg-gray-50 px-3 py-2 border-b border-gray-200 flex justify-between items-center">
							<span class="text-xs font-medium text-gray-700">Select Files</span>
							<button
								type="button"
								on:click={() => selectedFiles = []}
								class="text-xs text-blue-600 hover:text-blue-700"
							>
								Clear All
							</button>
						</div>
						<div class="max-h-48 overflow-y-auto p-2">
							{#if fileTree}
								<FileTreeNode 
									node={fileTree} 
									{selectedFiles}
									on:toggle={(e) => toggleFileSelection(e.detail)}
								/>
							{:else}
								<p class="text-xs text-gray-500 p-2">Loading files...</p>
							{/if}
						</div>
					</div>
				{/if}

				{#if error}
					<div class="p-2 bg-red-50 border border-red-200 rounded-md">
						<p class="text-red-700 text-xs">{error}</p>
					</div>
				{/if}
			</div>
		</div>

		<!-- Footer -->
		<div class="p-4 border-t border-gray-200 flex items-center justify-end gap-2">
			<button
				on:click={onClose}
				class="px-3 py-1.5 text-gray-700 hover:bg-gray-100 rounded-md transition-colors text-sm"
			>
				Cancel
			</button>
			<button
				on:click={handleGenerate}
				disabled={!prompt.trim()}
				class="px-4 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors text-sm font-medium"
			>
				Generate
			</button>
		</div>
	</div>
{/if}
