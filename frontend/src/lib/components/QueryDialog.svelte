<script lang="ts">
	import { currentProject, identifiedSections, generatedDiagrams, diagramCache } from '$lib/stores';
	import { generateSectionDiagram } from '$lib/api';
	import type { WikiSection } from '$lib/types';

	export let isOpen = false;
	export let onClose: () => void;

	let prompt = '';
	let selectedSectionId = '';
	let error = '';
	let generatingInBackground: Set<string> = new Set();
	let isGenerating = false;

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
				diagram_type: 'flowchart',
				key_concepts: []
			};
		}

		const sectionToGenerate = section;
		const projectPath = $currentProject;
		
		// Mark as generating
		generatingInBackground.add(sectionToGenerate.section_id);
		generatingInBackground = generatingInBackground;
		
		// Generate and wait for completion
		try {
			const diagram = await generateSectionDiagram(projectPath, sectionToGenerate);
			
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

				<!-- Section Selector -->
				<div>
					<label for="section" class="block text-xs font-medium text-gray-700 mb-1">
						Base on section (optional)
					</label>
					<select
						id="section"
						bind:value={selectedSectionId}
						class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
					>
						<option value="">New custom diagram</option>
						{#each $identifiedSections as section}
							<option value={section.section_id}>{section.section_title}</option>
						{/each}
					</select>
				</div>

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
