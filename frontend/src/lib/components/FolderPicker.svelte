<script lang="ts">
	import { currentProject, projectHistory, addToHistory, isAnalyzing, availableSections, openDiagramTab, generatedDiagrams, diagramCache } from '$lib/stores';
	import { identifyDiagramSections, generateSectionDiagram } from '$lib/api';

	let folderPath = '';
	let error = '';
	let generatingQueue: Set<string> = new Set();

	async function handleAnalyze() {
		if (!folderPath.trim()) {
			error = 'Please enter a folder path';
			return;
		}

		error = '';
		isAnalyzing.set(true);

		try {
			const result = await identifyDiagramSections(folderPath);
			currentProject.set(folderPath);
			availableSections.set(result.sections);
			addToHistory(folderPath);
			
			// Navigate to main view immediately
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
		}
	}

	async function checkCachedDiagrams(sections: any[]) {
		console.log('Checking for cached diagrams...');
		const cachedSections = [];
		const uncachedSections = [];
		
		// Check each section to see if it's already cached
		for (const section of sections) {
			try {
				console.log(`Checking cache for section: ${section.section_title}`);
				const diagram = await generateSectionDiagram(folderPath, section);
				// If successful, it's cached
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
				// Not cached or error - needs generation
				uncachedSections.push(section);
			}
			// Small delay to avoid overwhelming
			await new Promise(resolve => setTimeout(resolve, 100));
		}
		
		console.log(`Found ${cachedSections.length} cached, ${uncachedSections.length} need generation`);
		
		// Generate any uncached diagrams
		if (uncachedSections.length > 0) {
			generateDiagramsInBackground(uncachedSections);
		}
	}

	async function generateDiagramsInBackground(sections: any[]) {
		console.log(`Starting background generation of ${sections.length} diagrams...`);
		
		// Mark all as queued
		generatingQueue = new Set(sections.map(s => s.section_id));
		
		// Generate diagrams one by one
		for (let i = 0; i < sections.length; i++) {
			const section = sections[i];
			try {
				console.log(`Generating diagram ${i + 1}/${sections.length}: ${section.section_title}`);
				const diagram = await generateSectionDiagram(folderPath, section);
				
				// Remove from queue
				generatingQueue.delete(section.section_id);
				generatingQueue = generatingQueue;
				
				// Mark as generated in the store (for all diagrams, not just the first)
				generatedDiagrams.update(set => {
					const newSet = new Set(set);
					newSet.add(section.section_id);
					return newSet;
				});
				console.log(`Diagram ${section.section_id} marked as generated`);
				
				// Open the first diagram automatically
				if (i === 0) {
					openDiagramTab(diagram);
				}
			} catch (error) {
				console.error(`Failed to generate diagram for ${section.section_title}:`, error);
				generatingQueue.delete(section.section_id);
				generatingQueue = generatingQueue;
				// Continue with next section even if one fails
			}
			
			// Small delay between requests to avoid overwhelming the server
			if (i < sections.length - 1) {
				await new Promise(resolve => setTimeout(resolve, 500));
			}
		}
		
		console.log('All diagrams generated and cached');
		generatingQueue = new Set();
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
