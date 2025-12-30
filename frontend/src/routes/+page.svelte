<script lang="ts">
	import { currentProject, leftPanelOpen, rightPanelOpen, activeDiagram } from '$lib/stores';
	import FolderPicker from '$lib/components/FolderPicker.svelte';
	import DiagramTabs from '$lib/components/DiagramTabs.svelte';
	import LeftPanel from '$lib/components/LeftPanel.svelte';
	import RightPanel from '$lib/components/RightPanel.svelte';
	import DiagramViewer from '$lib/components/DiagramViewer.svelte';
	import QueryInput from '$lib/components/QueryInput.svelte';

	let leftPanelWidth = 250;
	let rightPanelWidth = 300;

	function toggleLeftPanel() {
		leftPanelOpen.update((open) => !open);
	}

	function toggleRightPanel() {
		rightPanelOpen.update((open) => !open);
	}
</script>

{#if !$currentProject}
	<FolderPicker />
{:else}
	<div class="h-screen flex flex-col">
		<!-- Top: Tabs -->
		<DiagramTabs />

		<!-- Main Content Area -->
		<div class="flex-1 flex overflow-hidden">
			<!-- Left Panel: Tree Structure -->
			{#if $leftPanelOpen}
				<div
					class="flex-shrink-0 border-r border-gray-200"
					style="width: {leftPanelWidth}px; min-width: 200px; max-width: 400px;"
				>
					<LeftPanel />
				</div>
			{/if}

			<!-- Toggle Left Panel Button -->
			<button
				on:click={toggleLeftPanel}
				class="flex-shrink-0 w-8 bg-gray-100 hover:bg-gray-200 flex items-center justify-center border-r border-gray-200"
				title={$leftPanelOpen ? 'Hide panel' : 'Show panel'}
			>
				<svg
					class="w-4 h-4 transform transition-transform"
					class:rotate-180={!$leftPanelOpen}
					fill="currentColor"
					viewBox="0 0 20 20"
				>
					<path
						fill-rule="evenodd"
						d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"
						clip-rule="evenodd"
					/>
				</svg>
			</button>

			<!-- Center: Diagram Viewer + Query Input -->
			<div class="flex-1 flex flex-col overflow-hidden">
				<div class="flex-1 overflow-hidden">
					{#if $activeDiagram}
						<DiagramViewer diagram={$activeDiagram} />
					{:else}
						<div class="h-full flex items-center justify-center text-gray-500">
							<p>Select a diagram section from the left panel</p>
						</div>
					{/if}
				</div>
				<QueryInput />
			</div>

			<!-- Toggle Right Panel Button -->
			<button
				on:click={toggleRightPanel}
				class="flex-shrink-0 w-8 bg-gray-100 hover:bg-gray-200 flex items-center justify-center border-l border-gray-200"
				title={$rightPanelOpen ? 'Hide panel' : 'Show panel'}
			>
				<svg
					class="w-4 h-4 transform transition-transform"
					class:rotate-180={$rightPanelOpen}
					fill="currentColor"
					viewBox="0 0 20 20"
				>
					<path
						fill-rule="evenodd"
						d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"
						clip-rule="evenodd"
					/>
				</svg>
			</button>

			<!-- Right Panel: Explanations -->
			{#if $rightPanelOpen}
				<div
					class="flex-shrink-0"
					style="width: {rightPanelWidth}px; min-width: 250px; max-width: 500px;"
				>
					<RightPanel />
				</div>
			{/if}
		</div>
	</div>
{/if}
