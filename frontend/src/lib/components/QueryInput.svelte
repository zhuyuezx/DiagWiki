<script lang="ts">
	import { currentProject, identifiedSections, diagramCache, openTabs, generatedDiagrams, selectedLanguage, updateProjectDiagramCount } from '$lib/stores';
	import { queryWikiProblemStream, generateSectionDiagram } from '$lib/api';

	let query = '';
	let isQuerying = false;
	let result: any = null;
	let error = '';
	let isExpanded = true;
	let isExecuting = false;
	let streamingText = '';
	let cancelStream: (() => void) | null = null;
	let isComposing = false; // Track IME composition state

	function handleSubmit() {
		if (!query.trim() || !$currentProject || isQuerying) return;

		isQuerying = true;
		error = '';
		result = null;
		streamingText = '';

		// Start streaming
		cancelStream = queryWikiProblemStream(
			$currentProject,
			query,
			// On chunk
			(chunk: string) => {
				streamingText += chunk;
			},
			// On complete
			(response: any) => {
				result = response;
				isExpanded = true;
				isQuerying = false;
				cancelStream = null;
			},
			// On error
			(errorMsg: string) => {
				error = errorMsg;
				isQuerying = false;
				cancelStream = null;
			},
			$selectedLanguage
		);
	}

	async function handleExecutePlan() {
		if (!result || !$currentProject || isExecuting) return;
		
		isExecuting = true;
		error = '';

		try {
			const modifications = result.modify || [];
			const creations = result.create || [];
			
			// Execute modifications first
			for (const mod of modifications) {
				try {
					const response = await fetch('http://localhost:8001/modifyOrCreateWiki', {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({
							root_path: $currentProject,
							next_step_prompt: mod.next_step_prompt,
							wiki_name: mod.wiki_name,
							is_new: false,
							language: $selectedLanguage
						})
					});
					if (!response.ok) {
						console.error(`Failed to modify ${mod.wiki_name}`);
					} else {
						const diagram = await response.json();
						
						// Update identifiedSections store with new details
						identifiedSections.update(map => {
							if (!$currentProject) return map;
							if (!map.has($currentProject)) return map;
							const newMap = new Map(map);
							const projectSections = newMap.get($currentProject) || [];
							const updatedSections = projectSections.map(s => {
								if (s.section_id === diagram.section_id) {
									return {
										section_id: diagram.section_id,
										section_title: diagram.section_title,
										section_description: diagram.section_description,
										diagram_type: diagram.diagram?.diagram_type || 'flowchart',
										key_concepts: s.key_concepts || []
									};
								}
								return s;
							});
							newMap.set($currentProject, updatedSections);
							return newMap;
						});
						
						// CRITICAL: Update cache with new diagram data
						diagramCache.update(cache => {
							const newCache = new Map(cache);
							newCache.set(diagram.section_id, diagram);
							return newCache;
						});
						
						// CRITICAL: Update open tab if it exists
						const tabIndex = $openTabs.findIndex(t => t.section_id === diagram.section_id);
						if (tabIndex !== -1) {
							openTabs.update(tabs => {
								const newTabs = [...tabs];
								newTabs[tabIndex] = diagram;
								return newTabs;
							});
						}
						
						// Mark as generated
						generatedDiagrams.update(set => {
							const newSet = new Set(set);
							newSet.add(diagram.section_id);
							return newSet;
						});
						
						// Update project history diagram count
						if ($currentProject) updateProjectDiagramCount($currentProject);
					}
				} catch (err) {
					console.error(`Error modifying ${mod.wiki_name}:`, err);
				}
			}
			
			// Execute creations
			for (const creation of creations) {
				try {
					const response = await fetch('http://localhost:8001/modifyOrCreateWiki', {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({
							root_path: $currentProject,
							next_step_prompt: creation.next_step_prompt,
							wiki_name: creation.wiki_name,
							is_new: true,
							language: $selectedLanguage
						})
					});
					
					if (response.ok) {
						const diagram = await response.json();
						
						// Add new section to identifiedSections
						identifiedSections.update(map => {
							if (!$currentProject) return map;
							const newMap = new Map(map);
							const projectSections = newMap.get($currentProject) || [];
							if (!projectSections.some(s => s.section_id === diagram.section_id)) {
								newMap.set($currentProject, [...projectSections, {
									section_id: diagram.section_id,
									section_title: diagram.section_title,
									section_description: diagram.section_description,
									diagram_type: diagram.diagram?.diagram_type || 'flowchart',
									key_concepts: []
								}]);
							}
							return newMap;
						});

						// CRITICAL: Add to cache
						diagramCache.update(cache => {
							const newCache = new Map(cache);
							newCache.set(diagram.section_id, diagram);
							return newCache;
						});
						
						// Mark as generated
						generatedDiagrams.update(set => {
							const newSet = new Set(set);
							newSet.add(diagram.section_id);
							return newSet;
						});
						
						// Update project history diagram count
						if ($currentProject) updateProjectDiagramCount($currentProject);
					}
				} catch (err) {
					console.error(`Error creating ${creation.wiki_name}:`, err);
				}
			}
			
			// Clear result to show success
			result = { 
				status: 'success',
				intent: 'question',
				answer: 'Plan executed successfully! New sections are now available in the left panel.'
			};
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to execute plan';
		} finally {
			isExecuting = false;
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey && !isComposing) {
			event.preventDefault();
			handleSubmit();
		}
	}

	function toggleExpand() {
		isExpanded = !isExpanded;
	}
	
	// Format plain text from answer (remove markdown formatting)
	function formatPlainText(text: string): string {
		if (!text) return '';
		// Remove markdown formatting
		return text
			.replace(/\*\*(.+?)\*\*/g, '$1') // Bold
			.replace(/\*(.+?)\*/g, '$1')     // Italic
			.replace(/`(.+?)`/g, '$1')       // Code
			.replace(/#+\s/g, '')            // Headers
			.replace(/\[(.+?)\]\(.+?\)/g, '$1'); // Links
	}
	
	// Format modification plan as plain text
	function formatPlan(result: any): string {
		let plan = '';
		
		if (result.reasoning) {
			plan += 'Reasoning: ' + formatPlainText(result.reasoning) + '\n\n';
		}
		
		if (result.modify && result.modify.length > 0) {
			plan += 'Modifications:\n';
			result.modify.forEach((mod: any, i: number) => {
				plan += `${i + 1}. ${mod.wiki_name}\n`;
				if (mod.reasoning) {
					plan += `   Reason: ${formatPlainText(mod.reasoning)}\n`;
				}
			});
			plan += '\n';
		}
		
		if (result.create && result.create.length > 0) {
			plan += 'New Sections to Create:\n';
			result.create.forEach((creation: any, i: number) => {
				plan += `${i + 1}. ${creation.wiki_name}\n`;
				if (creation.reasoning) {
					plan += `   Reason: ${formatPlainText(creation.reasoning)}\n`;
				}
			});
		}
		
		return plan;
	}
</script>

<div class="border-t border-gray-200 bg-white p-4">
	<div class="flex gap-2">
		<input
			type="text"
			bind:value={query}
			on:keydown={handleKeydown}
			on:compositionstart={() => isComposing = true}
			on:compositionend={() => isComposing = false}
			placeholder="Ask a question or request modifications..."
			class="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
			disabled={!$currentProject || isQuerying}
		/>
		<button
			on:click={handleSubmit}
			disabled={!$currentProject || isQuerying || !query.trim()}
			class="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors text-sm font-medium"
		>
			{isQuerying ? 'Querying...' : 'Ask'}
		</button>
	</div>

	{#if error}
		<div class="mt-2 p-3 bg-red-50 border border-red-200 rounded-md">
			<p class="text-red-700 text-sm">{error}</p>
		</div>
	{/if}

	{#if isQuerying && streamingText}
		<div class="mt-2 border border-blue-200 rounded-md bg-blue-50 overflow-hidden" style="max-height: 30vh;">
			<div class="px-3 py-2 bg-blue-100">
				<span class="text-xs font-semibold text-blue-700 uppercase">Generating Response...</span>
			</div>
			<div class="p-3 overflow-y-auto" style="max-height: calc(30vh - 40px);">
				<p class="text-sm text-gray-900 whitespace-pre-wrap">{streamingText}</p>
			</div>
		</div>
	{/if}

	{#if result}
		<div class="mt-2 border border-blue-200 rounded-md bg-blue-50 overflow-hidden" style="max-height: 30vh;">
			<button
				on:click={toggleExpand}
				class="w-full flex items-center justify-between px-3 py-2 bg-blue-100 hover:bg-blue-150 transition-colors"
			>
				<span class="text-xs font-semibold text-blue-700 uppercase">
					{result.intent === 'modification' ? 'Modification Plan' : 'Answer'}
				</span>
				<svg
					class="w-4 h-4 transform transition-transform {isExpanded ? 'rotate-180' : ''}"
					fill="currentColor"
					viewBox="0 0 20 20"
				>
					<path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
				</svg>
			</button>
			{#if isExpanded}
				<div class="p-3 overflow-y-auto" style="max-height: calc(30vh - 40px);">
					{#if result.intent === 'question'}
						<p class="text-sm text-gray-900 whitespace-pre-wrap">{formatPlainText(result.answer || '')}</p>
					{:else if result.intent === 'modification'}
						<p class="text-sm text-gray-900 whitespace-pre-wrap">{formatPlan(result)}</p>
						<div class="mt-3 pt-3 border-t border-blue-200">
							<button
								on:click={handleExecutePlan}
								disabled={isExecuting}
								class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors text-sm font-medium"
							>
								{isExecuting ? 'Executing...' : 'Confirm & Execute Plan'}
							</button>
						</div>
					{:else}
						<p class="text-sm text-gray-900">{JSON.stringify(result, null, 2)}</p>
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</div>
