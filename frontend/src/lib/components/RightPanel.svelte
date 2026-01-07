<script lang="ts">
	import { selectedElement, rightPanelOpen, activeDiagram, currentProject } from '$lib/stores';
	import { getDiagramReferences } from '$lib/api';
	import { onMount } from 'svelte';

	let activeTab: 'details' | 'references' = 'details';
	let sourceFiles: Array<{
		file: string;
		segments: Array<{
			start_line: number;
			end_line: number;
			preview: string;
		}>;
		relevance: string;
	}> = [];
	let loadingReferences = false;

	function handleClose() {
		rightPanelOpen.set(false);
		selectedElement.set(null);
	}

	// Fetch source files from API when diagram changes
	$: if ($activeDiagram && $currentProject) {
		fetchDiagramReferences($currentProject, $activeDiagram.section_id);
	}

	async function fetchDiagramReferences(projectPath: string, sectionId: string) {
		loadingReferences = true;
		try {
			const data = await getDiagramReferences(projectPath, sectionId);
			console.log('Fetched references:', data);
			sourceFiles = data.rag_sources || [];
		} catch (error) {
			console.error('Error fetching diagram references:', error);
			sourceFiles = [];
		} finally {
			loadingReferences = false;
		}
	}
</script>

{#if $selectedElement || $activeDiagram}
	<div class="h-full flex flex-col bg-white">
		<div class="p-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
			<h3 class="font-semibold text-gray-900">
				{$selectedElement ? ($selectedElement.type === 'node' ? 'Node' : 'Edge') : 'Diagram'} Details
			</h3>
			<button
				on:click={handleClose}
				class="p-1 hover:bg-gray-100 rounded"
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

		<!-- Tab Navigation -->
		<div class="flex border-b border-gray-200 flex-shrink-0">
			<button
				on:click={() => activeTab = 'details'}
				class="flex-1 px-4 py-2 text-sm font-medium transition-colors"
				class:text-blue-600={activeTab === 'details'}
				class:border-b-2={activeTab === 'details'}
				class:border-blue-600={activeTab === 'details'}
				class:text-gray-600={activeTab !== 'details'}
			>
				Details
			</button>
			<button
				on:click={() => activeTab = 'references'}
				class="flex-1 px-4 py-2 text-sm font-medium transition-colors"
				class:text-blue-600={activeTab === 'references'}
				class:border-b-2={activeTab === 'references'}
				class:border-blue-600={activeTab === 'references'}
				class:text-gray-600={activeTab !== 'references'}
			>
				References
				{#if sourceFiles.length > 0}
					<span class="ml-1 text-xs bg-gray-200 text-gray-700 px-1.5 py-0.5 rounded-full">
						{sourceFiles.length}
					</span>
				{/if}
			</button>
		</div>

		<!-- Tab Content -->
		<div class="flex-1 overflow-y-auto">
			{#if activeTab === 'details'}
				<div class="p-4">
					{#if $selectedElement}
						{#if $selectedElement.type === 'node'}
							<div class="space-y-4">
								<div>
									<label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Node ID</label>
									<p class="text-sm text-gray-900 mt-1 font-mono bg-gray-50 p-2 rounded">{$selectedElement.id}</p>
								</div>

								<div>
									<label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Label</label>
									<p class="text-sm text-gray-900 mt-1">{$selectedElement.data.label}</p>
								</div>

								<div>
									<label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Shape</label>
									<p class="text-sm text-gray-900 mt-1">
										<span class="inline-flex items-center px-2 py-1 rounded bg-blue-50 text-blue-700 text-xs font-medium">
											{$selectedElement.data.shape}
										</span>
									</p>
								</div>

								<div>
									<label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Explanation</label>
									<div class="text-sm text-gray-700 mt-2 leading-relaxed bg-blue-50 p-3 rounded border-l-4 border-blue-400">
										{$selectedElement.data.explanation || 'No explanation available.'}
									</div>
								</div>
							</div>
						{:else}
							<div class="space-y-4">
								<div>
									<label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Connection</label>
									<p class="text-sm text-gray-900 mt-1 font-mono bg-gray-50 p-2 rounded">{$selectedElement.id}</p>
								</div>

								<div>
									<label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Flow</label>
									<div class="mt-2 flex items-center gap-2">
										<span class="px-3 py-1 bg-green-50 text-green-700 rounded text-sm font-medium">
											{$selectedElement.data.source}
										</span>
										<svg class="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
											<path fill-rule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clip-rule="evenodd" />
										</svg>
										<span class="px-3 py-1 bg-purple-50 text-purple-700 rounded text-sm font-medium">
											{$selectedElement.data.target}
										</span>
									</div>
								</div>

								{#if $selectedElement.data.label}
									<div>
										<label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Label</label>
										<p class="text-sm text-gray-900 mt-1">{$selectedElement.data.label}</p>
									</div>
								{/if}

								<div>
									<label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Explanation</label>
									<div class="text-sm text-gray-700 mt-2 leading-relaxed bg-purple-50 p-3 rounded border-l-4 border-purple-400">
										{$selectedElement.data.explanation || 'No explanation available.'}
									</div>
								</div>
							</div>
						{/if}
					{:else if $activeDiagram}
						<!-- Show diagram-level details when no element is selected -->
						<div class="space-y-4">
							<div>
								<label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Diagram Type</label>
								<p class="text-sm text-gray-900 mt-1">
									<span class="inline-flex items-center px-2 py-1 rounded bg-gray-100 text-gray-700 text-xs font-medium">
										{$activeDiagram.diagram.diagram_type}
									</span>
								</p>
							</div>

							<div>
								<label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Description</label>
								<p class="text-sm text-gray-700 mt-1 leading-relaxed">{$activeDiagram.diagram.description}</p>
							</div>

							<div>
								<label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Structure</label>
								<div class="mt-2 grid grid-cols-2 gap-2">
									<div class="bg-blue-50 p-3 rounded">
										<div class="text-2xl font-bold text-blue-600">{Object.keys($activeDiagram.nodes).length}</div>
										<div class="text-xs text-gray-600">Nodes</div>
									</div>
									<div class="bg-purple-50 p-3 rounded">
										<div class="text-2xl font-bold text-purple-600">{Object.keys($activeDiagram.edges).length}</div>
										<div class="text-xs text-gray-600">Edges</div>
									</div>
								</div>
							</div>

							<div class="mt-4 p-3 bg-yellow-50 border-l-4 border-yellow-400 rounded">
								<p class="text-xs text-yellow-800">
									<strong>Tip:</strong> Click on nodes or edges in the diagram to see detailed explanations
								</p>
							</div>
						</div>
					{:else}
						<!-- No diagram selected -->
						<div class="text-center py-12">
							<svg class="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
							<p class="text-gray-500 text-sm">No diagram selected</p>
							<p class="text-gray-400 text-xs mt-1">Open a diagram to see details</p>
						</div>
					{/if}
				</div>
			{:else if activeTab === 'references'}
				<div class="p-4">
					<div class="text-sm text-gray-600 mb-4">
						<p class="mb-2">Source files used to generate this diagram from RAG analysis:</p>
					</div>

					{#if loadingReferences}
						<div class="flex items-center justify-center py-8">
							<svg class="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
								<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
								<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
							</svg>
						</div>
					{:else if sourceFiles.length > 0}
						<div class="space-y-3">
							{#each sourceFiles as source, i}
								<div class="p-3 bg-gray-50 rounded border border-gray-200">
									<div class="flex items-start gap-3">
										<span class="text-gray-400 text-xs font-mono mt-0.5 flex-shrink-0">{i + 1}</span>
										<div class="flex-1 min-w-0">
											<p class="text-sm font-mono text-gray-900 break-all font-semibold">{source.file}</p>
											
											{#if source.segments && source.segments.length > 0}
												<div class="mt-2 space-y-1">
													<p class="text-xs text-gray-600 font-medium">
														{source.segments.length} segment{source.segments.length > 1 ? 's' : ''}:
													</p>
													{#each source.segments as segment, j}
														<div class="ml-3 pl-3 border-l-2 border-blue-300 py-1">
															<p class="text-xs text-blue-600 font-mono">
																lines {segment.start_line}-{segment.end_line}
															</p>
															{#if segment.preview}
																<p class="text-xs text-gray-500 italic mt-0.5">{segment.preview}</p>
															{/if}
														</div>
													{/each}
												</div>
											{/if}
											
											{#if source.relevance}
												<p class="text-xs text-gray-600 mt-2">{source.relevance}</p>
											{/if}
										</div>
									</div>
								</div>
							{/each}
						</div>
					{:else}
						<div class="text-center py-8">
							<svg class="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
							</svg>
							<p class="text-sm text-gray-500">No references available</p>
							<p class="text-xs text-gray-400 mt-1">
								{#if !$activeDiagram}
									Open a diagram to see RAG source files
								{:else}
									This diagram was generated before references were tracked. Regenerate to see sources.
								{/if}
							</p>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	</div>
{/if}
