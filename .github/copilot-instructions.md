# SvelteKit Frontend Setup for DiagWiki

## Project Setup Checklist

- [x] Create copilot-instructions.md
- [ ] Scaffold SvelteKit project
- [ ] Install dependencies
- [ ] Create component structure
- [ ] Configure Tailwind CSS
- [ ] Create stores
- [ ] Create API integration
- [ ] Test build

## Project Overview
Creating a minimalist diagram visualization frontend using SvelteKit + TypeScript.

## Architecture
- **Framework**: SvelteKit with TypeScript
- **Styling**: Tailwind CSS
- **Diagrams**: Mermaid.js
- **State**: Svelte stores
- **Backend**: localhost:8001

## Components
1. FolderPicker - Initial screen for selecting project folder
2. HistoryList - Recent projects display
3. DiagramTabs - Browser-like tabs for multiple diagrams
4. LeftPanel - Collapsible tree structure
5. RightPanel - Collapsible explanation panel
6. DiagramViewer - Center panel with Mermaid diagram
7. QueryInput - Bottom input box
8. Layout - Main layout orchestrator
