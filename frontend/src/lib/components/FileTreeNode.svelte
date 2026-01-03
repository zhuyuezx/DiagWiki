<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	export let node: any;
	export let selectedFiles: string[];
	export let level: number = 0;

	const dispatch = createEventDispatcher();

	let isExpanded = level === 0; // Expand root by default

	function toggleExpand() {
		isExpanded = !isExpanded;
	}

	function handleToggle(filePath: string) {
		dispatch('toggle', filePath);
	}

	$: isSelected = node.type === 'file' && selectedFiles.includes(node.path);
	$: hasSelectedChildren = node.type === 'folder' && node.children?.some((child: any) => {
		if (child.type === 'file') return selectedFiles.includes(child.path);
		return hasSelectedDescendants(child);
	});

	function hasSelectedDescendants(folderNode: any): boolean {
		if (!folderNode.children) return false;
		return folderNode.children.some((child: any) => {
			if (child.type === 'file') return selectedFiles.includes(child.path);
			return hasSelectedDescendants(child);
		});
	}
</script>

{#if node}
	<div style="padding-left: {level * 12}px" class="text-xs">
		{#if node.type === 'folder'}
			<button
				type="button"
				on:click={toggleExpand}
				class="flex items-center gap-1 py-1 hover:bg-gray-100 rounded w-full text-left transition-colors {hasSelectedChildren ? 'font-medium' : ''}"
			>
				<svg class="w-3 h-3 transition-transform {isExpanded ? 'rotate-90' : ''}" fill="currentColor" viewBox="0 0 20 20">
					<path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
				</svg>
				<svg class="w-3 h-3 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
					<path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
				</svg>
				<span class="text-gray-700">{node.name}</span>
			</button>
			{#if isExpanded && node.children}
				{#each node.children as child (child.path)}
					<svelte:self 
						node={child} 
						{selectedFiles}
						level={level + 1}
						on:toggle
					/>
				{/each}
			{/if}
		{:else if node.type === 'file'}
			<button
				type="button"
				on:click={() => handleToggle(node.path)}
				class="flex items-center gap-1 py-1 hover:bg-gray-100 rounded w-full text-left transition-colors"
			>
				<input
					type="checkbox"
					checked={isSelected}
					on:click|stopPropagation
					class="w-3 h-3 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
				/>
				<svg class="w-3 h-3 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
					<path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd" />
				</svg>
				<span class="{isSelected ? 'text-blue-700 font-medium' : 'text-gray-600'}">{node.name}</span>
			</button>
		{/if}
	</div>
{/if}
