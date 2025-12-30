<script lang="ts">
	import { currentProject, identifiedSections, openTabs, activeTabIndex, closeDiagramTab, openDiagramTab } from '$lib/stores';
	import QueryDialog from './QueryDialog.svelte';
	import { onMount } from 'svelte';

	let showQueryDialog = false;

	function handleGoHome() {
		currentProject.set(null);
		identifiedSections.set([]);
		openTabs.set([]);
		activeTabIndex.set(0);
	}

	function handleTabClick(index: number) {
		activeTabIndex.set(index);
	}

	function handleCloseTab(event: MouseEvent, index: number) {
		event.stopPropagation();
		closeDiagramTab(index);
	}

	function handleOpenQueryDialog() {
		showQueryDialog = true;
	}

	function handleCloseQueryDialog() {
		showQueryDialog = false;
	}

	// Listen for custom diagram generation events
	onMount(() => {
		const handleOpenDiagram = (event: CustomEvent) => {
			openDiagramTab(event.detail);
		};
		
		window.addEventListener('openDiagram', handleOpenDiagram as EventListener);
		
		return () => {
			window.removeEventListener('openDiagram', handleOpenDiagram as EventListener);
		};
	});
</script>

<div class="flex items-center bg-gray-100 border-b border-gray-300">
	<!-- Home Button -->
	<button
		on:click={handleGoHome}
		class="flex-shrink-0 px-4 py-2 flex items-center gap-2 text-gray-600 hover:bg-gray-50 hover:text-gray-900 border-r border-gray-300 transition-colors"
		title="Return to home"
	>
		<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
		</svg>
		<span class="text-sm font-medium">Home</span>
	</button>
	
	<!-- Tabs container with overflow scroll -->
	<div class="flex items-center overflow-x-auto flex-1">
		{#if $openTabs.length > 0}
			{#each $openTabs as tab, index}
				<div
					class="relative flex items-center gap-2 px-4 py-2 border-r border-gray-300 hover:bg-gray-50 transition-colors min-w-[150px] max-w-[200px] flex-shrink-0"
					class:bg-white={$activeTabIndex === index}
					class:font-semibold={$activeTabIndex === index}
				>
					<button
						on:click={() => handleTabClick(index)}
						class="truncate flex-1 text-left text-sm"
					>
						{tab.section_title}
					</button>
					<button
						on:click={(e) => handleCloseTab(e, index)}
						class="p-1 hover:bg-gray-200 rounded flex-shrink-0"
						title="Close tab"
					>
						<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
							<path
								fill-rule="evenodd"
								d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
								clip-rule="evenodd"
							/>
						</svg>
					</button>
				</div>
			{/each}
		{/if}

		<!-- Add New Diagram Button (always visible) -->
		<button
			on:click={handleOpenQueryDialog}
			class="flex-shrink-0 px-3 py-2 flex items-center justify-center text-blue-600 hover:bg-blue-50 border-l border-gray-300 transition-colors"
			title="Generate custom diagram"
		>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
			</svg>
		</button>
	</div>
</div>

<!-- Query Dialog -->
<QueryDialog isOpen={showQueryDialog} onClose={handleCloseQueryDialog} />
