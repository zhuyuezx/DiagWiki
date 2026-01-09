<script lang="ts">
	import { currentProject, projectHistory, addToHistory, isAnalyzing, identifiedSections, openDiagramTab, generatedDiagrams, diagramCache, generateRequestSent, availableSections, failedSections, selectedLanguage, updateProjectDiagramCount } from '$lib/stores';
	import { identifyDiagramSections, generateSectionDiagram } from '$lib/api';
	import { retryWithBackoff, RETRY_MAX } from '$lib/retry';
	import type { WikiSection } from '$lib/types';

	let folderPath = '';
	let error = '';
	
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
	
	// Handle file picker (picks a directory)
	async function handleFilePicker() {
		try {
			const input = document.createElement('input');
			input.type = 'file';
			(input as any).webkitdirectory = true;
			(input as any).directory = true;
			input.multiple = true;
			
			input.onchange = (e: Event) => {
				const target = e.target as HTMLInputElement;
				if (target.files && target.files.length > 0) {
					const file = target.files[0];
					// Extract directory path from the file path
					const pathParts = file.webkitRelativePath.split('/');
					if (pathParts.length > 1) {
						// For security, we can't get the full path, but we can show the folder name
						const folderName = pathParts[0];
						error = `Due to security restrictions, browsers cannot reveal the full path. Selected folder: "${folderName}". Please enter the full path manually above.`;
					}
				}
			};
			
			input.click();
		} catch (err) {
			console.error('File picker error:', err);
			error = 'File picker not supported in this browser. Please enter path manually.';
		}
	}

	async function handleAnalyze() {
		if (!folderPath.trim()) {
			error = 'Please enter a folder path';
			return;
		}

		error = '';
		isAnalyzing.set(true);

		try {
			currentProject.set(folderPath);
			
			const result = await identifyDiagramSections(folderPath, $selectedLanguage);
			// Store sections in map keyed by project path
			identifiedSections.update(map => {
				const newMap = new Map(map);
				newMap.set(folderPath, result.sections);
				return newMap;
			});
			
			addToHistory(folderPath);
			
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
			identifiedSections.update(map => {
				const newMap = new Map(map);
				newMap.delete(folderPath);
				return newMap;
			});
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
				const diagram = await retryWithBackoff(() => generateSectionDiagram(folderPath, section, undefined, $selectedLanguage), section.section_id);

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
			const diagram = await retryWithBackoff(() => generateSectionDiagram(folderPath, section, undefined, $selectedLanguage), section.section_id);
			
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

<div class="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
	<div class="w-full max-w-6xl">
		<div class="text-center mb-12">
			<h1 class="text-5xl font-bold text-gray-900 mb-3">DiagWiki</h1>
			<p class="text-xl text-gray-600">Generate interactive diagrams from your codebase</p>
		</div>

		<!-- Folder Input Card -->
		<div class="bg-white rounded-xl shadow-lg p-8 mb-8">
			<div class="mb-6">
				<!-- Folder Path Input with Language Selector -->
				<div class="relative">
					<label for="folder" class="block text-sm font-semibold text-gray-700 mb-3">
						Project Folder Path
					</label>
					<div class="flex gap-3">
						<input
							id="folder"
							type="text"
							bind:value={folderPath}
							placeholder="/path/to/your/project"
							class="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-base"
							on:keydown={(e) => e.key === 'Enter' && handleAnalyze()}
						/>
						<select
							bind:value={$selectedLanguage}
							class="px-3 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-base bg-white"
							title="Documentation Language"
						>
							{#each languages as lang}
								<option value={lang.code}>{lang.name}</option>
							{/each}
						</select>
						<button
							on:click={handleFilePicker}
							class="px-4 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors border border-gray-300"
							title="Browse for folder"
						>
							<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
							</svg>
						</button>
					</div>
				</div>
			</div>

			<button
				on:click={handleAnalyze}
				disabled={$isAnalyzing}
				class="w-full px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
			>
				{$isAnalyzing ? 'Analyzing...' : 'Analyze'}
			</button>
			
			{#if error}
				<div class="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
					{error}
				</div>
			{/if}

		</div>

		<!-- Recent Projects -->
		{#if $projectHistory.length > 0}
			<div>
				<h2 class="text-2xl font-semibold text-gray-900 mb-6">Recent Projects</h2>
				<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
					{#each $projectHistory as project}
						<button
							on:click={() => handleSelectHistory(project.path)}
							class="bg-white rounded-xl shadow-md p-6 hover:shadow-xl transition-all duration-200 text-left group border-2 border-transparent hover:border-blue-300"
						>
							<div class="flex items-start justify-between mb-3">
								<div class="p-2 bg-blue-100 rounded-lg group-hover:bg-blue-200 transition-colors">
									<svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
									</svg>
								</div>
								{#if project.diagrams && project.diagrams.length > 0}
									<span class="px-2 py-1 bg-green-100 text-green-800 text-xs font-semibold rounded-full">
										{project.diagrams.length} diagrams
									</span>
								{/if}
							</div>
							<h3 class="font-semibold text-gray-900 mb-1 text-lg truncate">
								{project.path.split('/').pop() || 'Project'}
							</h3>
							<p class="text-sm text-gray-500 truncate mb-2">{project.path}</p>
							<p class="text-xs text-gray-400">
								Last accessed: {new Date(project.lastAccessed).toLocaleDateString()}
							</p>
						</button>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</div>
