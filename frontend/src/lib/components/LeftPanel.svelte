<script lang="ts">
	import { identifiedSections, currentProject, openDiagramTab, openTabs, generatedDiagrams, activeTabIndex, diagramCache, failedSections, corruptedDiagrams, selectedLanguage } from '$lib/stores';
	import { generateSectionDiagram, fixCorruptedDiagram } from '$lib/api';
	import type { WikiSection } from '$lib/types';
	import TreeNode from './TreeNode.svelte';
	import QueryDialog from './QueryDialog.svelte';
	import { retryWithBackoff } from '$lib/retry';

	let showQueryDialog = false;

	const languages = [
		{ code: 'en', name: '🇬🇧 EN' },
		{ code: 'zh', name: '🇨🇳 ZH' },
		{ code: 'es', name: '🇪🇸 ES' },
		{ code: 'ja', name: '🇯🇵 JA' },
		{ code: 'kr', name: '🇰🇷 KR' },
		{ code: 'vi', name: '🇻🇳 VI' },
		{ code: 'pt', name: '🇵🇹 PT' },
		{ code: 'fr', name: '🇫🇷 FR' },
		{ code: 'ru', name: '🇷🇺 RU' }
	];

	function handleOpenQueryDialog() {
		showQueryDialog = true;
	}

	function handleCloseQueryDialog() {
		showQueryDialog = false;
	}

	type ViewMode = 'diagrams' | 'tree';
	type FolderNode = {
		name: string;
		type: 'file' | 'folder';
		path: string;
		children?: FolderNode[];
	};

	let viewMode: ViewMode = 'diagrams';
	let expandedGroups: Set<string> = new Set(['flowchart', 'sequence', 'class', 'stateDiagram', 'erDiagram']);
	let expandedFolders: Set<string> = new Set(); // For folder tree view
	let folderTree: FolderNode | null = null;
	let loadingFolderTree = false;

	async function handleSectionClick(section: WikiSection) {
		if (!$currentProject || !$generatedDiagrams.has(section.section_id)) {
			return;
		}
		
		// Check if already open in a tab
		const existingTabIndex = $openTabs.findIndex(t => t.section_id === section.section_id);
		if (existingTabIndex !== -1) {
			activeTabIndex.set(existingTabIndex);
			return;
		}

		// Check frontend cache first - access the Map reactively
		const cache = $diagramCache;
		if (cache.has(section.section_id)) {
			const cachedDiagram = cache.get(section.section_id)!;
			openDiagramTab(cachedDiagram);
			return;
		}

		try {
			const diagram = await generateSectionDiagram($currentProject, section, undefined, $selectedLanguage);
			
			// Cache is updated by openDiagramTab
			openDiagramTab(diagram);
		} catch (error) {
			console.error('Failed to load diagram:', error);
			alert('Failed to load diagram');
		}
	}
	
	// Check if diagram has been generated (is ready/cached)
	$: isReady = (sectionId: string): boolean => {
		return $generatedDiagrams.has(sectionId);
	};
	
	// Check if section failed
	$: isFailed = (sectionId: string): boolean => {
		if (!$currentProject) return false;
		return $failedSections.get($currentProject)?.has(sectionId) || false;
	};
	
	// Check if diagram has rendering errors
	$: isCorrupted = (sectionId: string): boolean => {
		return $corruptedDiagrams.has(sectionId);
	};
	
	// Handle fix for corrupted diagrams
	async function handleFixDiagram(section: WikiSection, event: Event) {
		event.stopPropagation();
		
		if (!$currentProject) return;
		
		console.log('Fix diagram - initial state:', {
			section,
			corruptedDiagramsCount: $corruptedDiagrams.size,
			corruptedDiagramIds: Array.from($corruptedDiagrams.keys()),
			diagramCacheCount: $diagramCache.size,
			diagramCacheIds: Array.from($diagramCache.keys())
		});
		
		// The section might be corrupted (undefined fields), so we need to find it by matching
		// against corrupted diagrams and cache entries
		let sectionId = section?.section_id;
		let cachedDiagram = null;
		let errorMessage = null;
		
		// If section_id is undefined, try to find it by iterating corrupted diagrams
		if (!sectionId) {
			console.warn('Section has undefined section_id, searching corrupted diagrams...');
			
			// Get valid corrupted diagram entries (filter out undefined keys)
			const validCorruptedEntries = Array.from($corruptedDiagrams.entries()).filter(([id]) => id !== undefined && id !== 'undefined' && id !== null);
			
			// If there's only one valid corrupted diagram, use that
			if (validCorruptedEntries.length === 1) {
				const [id, error] = validCorruptedEntries[0];
				sectionId = id;
				cachedDiagram = $diagramCache.get(id);
				errorMessage = error;
				console.log('Using the only valid corrupted diagram:', { sectionId, hasCache: !!cachedDiagram });
			} else {
				// Try to match by diagram_type
				for (const [id, error] of validCorruptedEntries) {
					const cached = $diagramCache.get(id);
					console.log('Checking corrupted diagram:', { id, hasCached: !!cached, cachedType: cached?.diagram?.diagram_type, sectionType: section.diagram_type });
					
					if (cached && cached.diagram?.diagram_type === section.diagram_type) {
						sectionId = id;
						cachedDiagram = cached;
						errorMessage = error;
						console.log('Found matching corrupted diagram by type:', { sectionId });
						break;
					}
				}
			}
		} else {
			errorMessage = $corruptedDiagrams.get(sectionId);
			cachedDiagram = $diagramCache.get(sectionId);
		}
		
		if (!sectionId) {
			console.error('Cannot determine section_id:', { 
				section, 
				corruptedDiagrams: Array.from($corruptedDiagrams.entries()),
				diagramCache: Array.from($diagramCache.entries()).map(([k, v]) => ({ id: k, hasData: !!v }))
			});
			alert('Error: Cannot identify corrupted diagram - section_id not found.');
			return;
		}
		
		if (!cachedDiagram) {
			console.error('No cached diagram found for section_id:', sectionId);
			alert(`Error: No cached diagram data found for ${sectionId}.`);
			return;
		}
		
		if (!errorMessage) {
			console.error('No error message found for section_id:', sectionId);
			alert(`Error: No error message found for ${sectionId}.`);
			return;
		}
		
		// Build complete section data from cache (which has the correct data)
		const sectionData = {
			section_id: cachedDiagram.section_id || sectionId,
			section_title: cachedDiagram.section_title || sectionId,
			section_description: cachedDiagram.section_description || 'Diagram description',
			diagram_type: cachedDiagram.diagram?.diagram_type || section.diagram_type || 'flowchart',
			key_concepts: section.key_concepts || []
		};
		
		console.log('Fixing diagram with reconstructed data:', sectionData);
		
		try {
			const fixedDiagram = await fixCorruptedDiagram(
				$currentProject,
				sectionData,
				cachedDiagram.diagram.mermaid_code,
				errorMessage,
				$selectedLanguage
			);
			
			if (fixedDiagram.status === 'success') {
				// Remove from corrupted set FIRST
				corruptedDiagrams.update(map => {
					const newMap = new Map(map);
					newMap.delete(section.section_id);
					return newMap;
				});
				
				// Update cache with fixed diagram
				diagramCache.update(cache => {
					const newCache = new Map(cache);
					newCache.set(section.section_id, fixedDiagram);
					return newCache;
				});
				
				// Update open tab if it exists - THIS IS CRITICAL
				const tabIndex = $openTabs.findIndex(t => t.section_id === section.section_id);
				if (tabIndex !== -1) {
					openTabs.update(tabs => {
						const newTabs = [...tabs];
						newTabs[tabIndex] = fixedDiagram;
						return newTabs;
					});
				}
			} else {
				throw new Error(fixedDiagram.error || 'Fix failed');
			}
		} catch (error) {
			console.error(`[${section.section_id}] Fix failed:`, error);
			alert(`Failed to fix diagram: ${error instanceof Error ? error.message : 'Unknown error'}`);
		}
	}
	
	// Handle retry for failed sections
	async function handleRetry(section: WikiSection, event: Event) {
		event.stopPropagation();
		
		if (!$currentProject) return;
		
		console.log(`[${section.section_id}] Manual retry initiated...`);
		
		// Remove from failed set temporarily
		failedSections.update(map => {
			const failedSet = map.get($currentProject);
			if (failedSet) {
				failedSet.delete(section.section_id);
				if (failedSet.size === 0) {
					map.delete($currentProject);
				} else {
					map.set($currentProject, failedSet);
				}
			}
			return map;
		});
		
		try {
			// Import shared retry logic
			const diagram = await retryWithBackoff(() => generateSectionDiagram($currentProject, section, undefined, $selectedLanguage), section.section_id);
			
			// Success - update stores
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
		} catch (error) {
			console.error(`[${section.section_id}] All retries failed:`, error);
			
			// Add back to failed set
			failedSections.update(map => {
				const failedSet = map.get($currentProject) || new Set<string>();
				failedSet.add(section.section_id);
				map.set($currentProject, failedSet);
				return map;
			});
			
			alert(`Failed to regenerate after 3 attempts: ${error instanceof Error ? error.message : 'Unknown error'}`);
		}
	}
	
	function toggleGroup(groupName: string) {
		if (expandedGroups.has(groupName)) {
			expandedGroups.delete(groupName);
		} else {
			expandedGroups.add(groupName);
		}
		expandedGroups = expandedGroups; // Trigger reactivity
	}

	// Group sections by diagram type
	// Get sections for the current project
	$: projectSections = $currentProject ? ($identifiedSections.get($currentProject) || []) : [];

	$: groupedSections = projectSections.reduce((acc, section) => {
		const type = section.diagram_type || 'other';
		if (!acc[type]) {
			acc[type] = [];
		}
		acc[type].push(section);
		return acc;
	}, {} as Record<string, WikiSection[]>);

	// Check if section is currently open
	function isOpen(sectionId: string): boolean {
		return $openTabs.some(tab => tab.section_id === sectionId);
	}

	// Diagram type display names
	const typeNames: Record<string, string> = {
		flowchart: 'Flowcharts',
		sequence: 'Sequence Diagrams',
		class: 'Class Diagrams',
		stateDiagram: 'State Diagrams',
		erDiagram: 'ER Diagrams',
		other: 'Other'
	};

	// Fetch folder tree from API when project changes
	$: if ($currentProject) {
		fetchFolderTree($currentProject);
	}

	async function fetchFolderTree(projectPath: string) {
		loadingFolderTree = true;
		try {
			const response = await fetch('http://localhost:8001/getFolderTree', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({
					root_path: projectPath
				})
			});

			if (response.ok) {
				const data = await response.json();
				folderTree = data.tree;
				// Expand all folders by default
				expandedFolders = collectAllFolderPaths(folderTree);
			} else {
				console.error('Failed to fetch folder tree:', response.statusText);
				folderTree = null;
			}
		} catch (error) {
			console.error('Error fetching folder tree:', error);
			folderTree = null;
		} finally {
			loadingFolderTree = false;
		}
	}

	function collectAllFolderPaths(node: FolderNode | null): Set<string> {
		const paths = new Set<string>();
		if (!node) return paths;
		
		if (node.type === 'folder') {
			paths.add(node.path);
			if (node.children) {
				for (const child of node.children) {
					const childPaths = collectAllFolderPaths(child);
					childPaths.forEach(p => paths.add(p));
				}
			}
		}
		return paths;
	}
</script>

<div class="h-full flex flex-col bg-gray-50">
	<div class="p-3 border-b border-gray-200">
		<div class="flex items-center justify-between mb-2">
			<h3 class="font-semibold text-gray-900">
				{viewMode === 'diagrams' ? 'Diagram Sections' : 'Folder Structure'}
			</h3>
			<button
				on:click={() => viewMode = viewMode === 'diagrams' ? 'tree' : 'diagrams'}
				class="text-xs px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 text-black-600 transition-colors"
				title="Toggle view"
			>
				{viewMode === 'diagrams' ? 'Tree View' : 'Diagram View'}
			</button>
		</div>
		{#if viewMode === 'diagrams'}
			<p class="text-xs text-gray-500">
				{projectSections.length} diagram{projectSections.length !== 1 ? 's' : ''}
			</p>
			<button
				on:click={handleOpenQueryDialog}
				class="mt-2 w-full px-3 py-2 text-black-600 text-sm font-medium rounded bg-blue-50 hover:bg-blue-100 transition-colors flex items-center justify-center gap-2"
				title="Generate custom diagram"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
				</svg>
				Generate Custom Diagram
			</button>
		{:else}
			<p class="text-xs text-gray-500">
				{$currentProject?.split('/').pop() || 'Project'}
			</p>
			<button
				on:click={handleOpenQueryDialog}
				class="mt-2 w-full px-3 py-2 text-black-600 text-sm font-medium rounded bg-blue-50 hover:bg-blue-100 transition-colors flex items-center justify-center gap-2"
				title="Generate custom diagram"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
				</svg>
				Generate Custom Diagram
			</button>
		{/if}
	</div>

	<div class="flex-1 overflow-y-auto">
		{#if viewMode === 'tree'}
			<!-- Folder Tree View -->
			<div class="p-2">
				{#if loadingFolderTree}
					<div class="flex items-center justify-center py-8">
						<svg class="animate-spin h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24">
							<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
							<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
						</svg>
					</div>
				{:else if folderTree}
					<div class="space-y-0.5">
						<TreeNode node={folderTree} bind:expandedFolders />
					</div>
				{:else}
					<p class="text-sm text-gray-500 text-center py-8">No project selected</p>
				{/if}
			</div>
		{:else}
			<!-- Diagram View -->
			{#if projectSections.length === 0}
				<div class="text-center text-gray-500 text-sm py-8 px-4">
					<!-- Loading Spinner -->
					<div class="flex justify-center items-center">
						<svg class="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
							<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
							<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
						</svg>
					</div>
					<p class="mt-3 text-gray-600">Loading sections...</p>
				</div>
			{:else}
				<!-- Tree structure -->
				<div class="py-2">
					{#each Object.entries(groupedSections) as [type, sections]}
					<div class="mb-1">
						<!-- Group header -->
						<button
							on:click={() => toggleGroup(type)}
							class="w-full flex items-center gap-2 px-4 py-2 hover:bg-gray-100 text-left"
						>
							<svg
								class="w-4 h-4 transform transition-transform"
								class:rotate-90={expandedGroups.has(type)}
								fill="currentColor"
								viewBox="0 0 20 20"
							>
								<path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
							</svg>
							<span class="text-sm font-medium text-gray-700">{typeNames[type] || type}</span>
							<span class="text-xs text-gray-500 ml-auto">{sections.length}</span>
						</button>

						<!-- Group items -->
						{#if expandedGroups.has(type)}
							<div class="ml-6 space-y-1 mt-1">
								{#each sections as section}
									<div
										class="w-full px-3 py-2 rounded transition-colors group relative"
										class:bg-blue-50={isOpen(section.section_id)}
										class:bg-red-50={isFailed(section.section_id)}
										class:bg-orange-50={isCorrupted(section.section_id)}
										class:border-l-2={isOpen(section.section_id) || isFailed(section.section_id) || isCorrupted(section.section_id)}
										class:border-blue-500={isOpen(section.section_id)}
										class:border-red-500={isFailed(section.section_id)}
										class:border-orange-500={isCorrupted(section.section_id)}
									>
										<button
											on:click={() => handleSectionClick(section)}
											disabled={!isReady(section.section_id) && !isFailed(section.section_id)}
											class="w-full text-left"
											class:hover:opacity-80={isReady(section.section_id)}
											class:cursor-wait={!isReady(section.section_id) && !isFailed(section.section_id)}
										>
											<div class="flex items-start gap-2">
												<div class="flex-1 min-w-0">
													<div class="text-sm font-medium text-gray-900 flex items-center gap-2" title="{section.section_title}">
														<span class="truncate">{section.section_title}</span>
														{#if isFailed(section.section_id)}
															<span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800 flex-shrink-0">
																Failed
															</span>
														{:else if isCorrupted(section.section_id)}
															<span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800 flex-shrink-0">
																Error
															</span>
														{:else if !isReady(section.section_id)}
															<span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800 flex-shrink-0">
																Loading...
															</span>
														{/if}
													</div>
												</div>
											</div>
										</button>
										<!-- Action buttons outside the clickable area -->
										{#if isFailed(section.section_id)}
											<div class="flex items-center gap-2 mt-1">
												<span class="text-xs text-red-600">
													Generation failed after 3 attempts
												</span>
												<button
													on:click={(e) => handleRetry(section, e)}
													class="text-xs px-2 py-0.5 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
												>
													Retry
												</button>
											</div>
										{:else if isCorrupted(section.section_id)}
											<div class="flex items-center gap-2 mt-1">
												<span class="text-xs text-orange-600">
													Diagram has rendering errors
												</span>
												<button
													on:click={(e) => handleFixDiagram(section, e)}
													class="text-xs px-2 py-0.5 bg-orange-600 text-white rounded hover:bg-orange-700 transition-colors"
												>
													Fix
												</button>
											</div>
										{:else if !isReady(section.section_id)}
											<div class="text-xs text-gray-500 mt-1">
												Queued for generation...
											</div>
										{/if}
									</div>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
			</div>
			{/if}
		{/if}
	</div>
	
	<!-- Language Selector at Bottom -->
	<div class="p-3 border-t border-gray-200 bg-white">
		<div class="flex items-center gap-2">
			<label for="lang" class="text-xs text-gray-600 font-medium">Lang:</label>
			<select
				id="lang"
				bind:value={$selectedLanguage}
				class="flex-1 px-2 py-1 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white"
			>
				{#each languages as lang}
					<option value={lang.code}>{lang.name}</option>
				{/each}
			</select>
		</div>
	</div>
</div>

<!-- Query Dialog -->
<QueryDialog isOpen={showQueryDialog} onClose={handleCloseQueryDialog} />
