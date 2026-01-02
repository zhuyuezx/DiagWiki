<script lang="ts">
	import { currentProject, projectHistory, addToHistory, isAnalyzing, identifiedSections, openDiagramTab, generatedDiagrams, diagramCache, generateRequestSent, availableSections, failedSections } from '$lib/stores';
	import { identifyDiagramSections, generateSectionDiagram } from '$lib/api';
	import { retryWithBackoff, RETRY_MAX } from '$lib/retry';
	import type { WikiSection } from '$lib/types';

	let folderPath = '';
	let error = '';

	async function handleAnalyze() {
		if (!folderPath.trim()) {
			error = 'Please enter a folder path';
			return;
		}

		error = '';
		isAnalyzing.set(true);

		try {
			currentProject.set(folderPath);
			addToHistory(folderPath);
			
			const result = await identifyDiagramSections(folderPath);
			identifiedSections.set(result.sections);
			
			// Stop analyzing state
			isAnalyzing.set(false);
			
			// Check which diagrams are already cached
			if (result.sections && result.sections.length > 0) {
				// Use setTimeout to make this truly async and non-blocking
				setTimeout(() => {
					checkCachedDiagrams(result.sections);
				}, 100);
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to analyze project';
			isAnalyzing.set(false);
			// Reset currentProject on error to go back to FolderPicker
			currentProject.set(null);
			identifiedSections.set([]);
		}
	}

	async function checkCachedDiagrams(sections: any[]) {
		console.log('Checking for cached diagrams...');
		const cachedSections = [];
		const uncachedSections = [];
		const errorSections = [];
		
		// Check each section to see if it's already cached
		for (const section of sections) {
			if ($availableSections.get(folderPath)?.has(section.section_id)) {
				// Already available
				cachedSections.push(section);
				continue;
			}
			if ($generateRequestSent.get(folderPath)?.has(section.section_id)) {
				// Request already sent for generation
				uncachedSections.push(section);
				continue;
			}
			try {
				generateRequestSent.update(map => {
					const requestSent = map.get(folderPath) || new Set<string>();
					requestSent.add(section.section_id);
					map.set(folderPath, requestSent);
					return map;
				});
				
				// Use retry wrapper instead of direct call
				const diagram = await retryWithBackoff(() => generateSectionDiagram(folderPath, section), section.section_id);

				availableSections.update(map => {
					const sectionsSet = map.get(folderPath) || new Set<WikiSection>();
					sectionsSet.add(section);
					map.set(folderPath, sectionsSet);
					return map;
				});
				cachedSections.push(section);
				
				// Add to frontend cache
				diagramCache.update(cache => {
					const newCache = new Map(cache);
					newCache.set(section.section_id, diagram);
					return newCache;
				});
				
				generatedDiagrams.update(set => {
					const newSet = new Set(set);
					newSet.add(section.section_id);
					return newSet;
				});
				
				// Open first diagram
				if (cachedSections.length === 1) {
					openDiagramTab(diagram);
				}
			} catch (error) {
				// All retries exhausted - mark as error
				console.error(`[${section.section_id}] Failed after ${RETRY_MAX} attempts`);
				errorSections.push(section);
				
				// Update failedSections store
				failedSections.update(map => {
					const failedSet = map.get(folderPath) || new Set<string>();
					failedSet.add(section.section_id);
					map.set(folderPath, failedSet);
					return map;
				});
			}
		}
		
		console.log(`Found ${cachedSections.length} cached, ${errorSections.length} failed after retries.`);
	}

	// Force retry a failed section
	export async function retryFailedSection(section: any) {
		if (!folderPath) return;
		
		console.log(`[${section.section_id}] Manual retry initiated...`);
		
		// Remove from failed set
		failedSections.update(map => {
			const failedSet = map.get(folderPath);
			if (failedSet) {
				failedSet.delete(section.section_id);
				if (failedSet.size === 0) {
					map.delete(folderPath);
				} else {
					map.set(folderPath, failedSet);
				}
			}
			return map;
		});
		
		try {
			const diagram = await retryWithBackoff(() => generateSectionDiagram(folderPath, section), section.section_id);
			
			availableSections.update(map => {
				const sectionsSet = map.get(folderPath) || new Set<WikiSection>();
				sectionsSet.add(section);
				map.set(folderPath, sectionsSet);
				return map;
			});
			
			diagramCache.update(cache => {
				const newCache = new Map(cache);
				newCache.set(section.section_id, diagram);
				return newCache;
			});
			
			generatedDiagrams.update(set => {
				const newSet = new Set(set);
				newSet.add(section.section_id);
				return newSet;
			});
			
			openDiagramTab(diagram);
			console.log(`[${section.section_id}] Retry successful!`);
		} catch (error) {
			console.error(`[${section.section_id}] Retry failed:`, error);
			// Add back to failed set
			failedSections.update(map => {
				const failedSet = map.get(folderPath) || new Set<string>();
				failedSet.add(section.section_id);
				map.set(folderPath, failedSet);
				return map;
			});
			throw error;
		}
	}

	function handleSelectHistory(path: string) {
		folderPath = path;
		handleAnalyze();
	}
</script>

<div class="flex flex-col items-center justify-center min-h-screen bg-gray-50 p-8">
	<div class="w-full max-w-2xl">
		<h1 class="text-4xl font-bold text-gray-900 mb-2">DiagWiki</h1>
		<p class="text-gray-600 mb-8">Generate interactive diagrams from your codebase</p>

		<!-- Folder Input -->
		<div class="bg-white rounded-lg shadow-sm p-6 mb-6">
			<label for="folder" class="block text-sm font-medium text-gray-700 mb-2">
				Project Folder Path
			</label>
			<div class="flex gap-2">
				<input
					id="folder"
					type="text"
					bind:value={folderPath}
					placeholder="/path/to/your/project"
					class="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
					on:keydown={(e) => e.key === 'Enter' && handleAnalyze()}
				/>
				<button
					on:click={handleAnalyze}
					disabled={$isAnalyzing}
					class="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
				>
					{$isAnalyzing ? 'Analyzing...' : 'Analyze'}
				</button>
			</div>
			{#if error}
				<p class="text-red-600 text-sm mt-2">{error}</p>
			{/if}
		</div>

		<!-- Recent Projects -->
		{#if $projectHistory.length > 0}
			<div class="bg-white rounded-lg shadow-sm p-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">Recent Projects</h2>
				<div class="space-y-2">
					{#each $projectHistory as project}
						<button
							on:click={() => handleSelectHistory(project.path)}
							class="w-full text-left px-4 py-3 border border-gray-200 rounded-md hover:bg-gray-50 transition-colors"
						>
							<div class="font-medium text-gray-900">{project.path.split('/').pop()}</div>
							<div class="text-sm text-gray-500">{project.path}</div>
						</button>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</div>
