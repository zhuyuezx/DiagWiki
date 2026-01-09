const API_BASE = 'http://localhost:8001';

export async function initWiki(rootPath: string) {
	const response = await fetch(`${API_BASE}/initWiki`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			root_path: rootPath
		})
	});

	if (!response.ok) {
		throw new Error(`Failed to initialize wiki: ${response.statusText}`);
	}

	return await response.json();
}

export async function identifyDiagramSections(rootPath: string, language: string = 'en') {
	// First ensure the database is initialized
	try {
		await initWiki(rootPath);
	} catch (error) {
		console.error('Failed to initialize wiki:', error);
		// Continue anyway - initWiki might fail if already exists
	}

	const response = await fetch(`${API_BASE}/identifyDiagramSections`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			root_path: rootPath,
			language: language
		})
	});

	if (!response.ok) {
		throw new Error(`Failed to identify sections: ${response.statusText}`);
	}

	return await response.json();
}

export async function generateSectionDiagram(rootPath: string, section: any, referenceFiles?: string[], language?: string) {
	const response = await fetch(`${API_BASE}/generateSectionDiagram`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			root_path: rootPath,
			section_id: section.section_id,
			section_title: section.section_title,
			section_description: section.section_description,
			diagram_type: section.diagram_type,
			key_concepts: section.key_concepts,
			language: language || 'en',
			reference_files: referenceFiles
		})
	});

	if (!response.ok) {
		throw new Error(`Failed to generate diagram: ${response.statusText}`);
	}

	return await response.json();
}

export async function fixCorruptedDiagram(
	rootPath: string,
	section: any,
	corruptedDiagram: string,
	errorMessage: string,
	language?: string
) {
	const response = await fetch(`${API_BASE}/fixCorruptedDiagram`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			root_path: rootPath,
			section_id: section.section_id,
			section_title: section.section_title,
			section_description: section.section_description,
			diagram_type: section.diagram_type,
			key_concepts: section.key_concepts || [],
			language: language || 'en',
			corrupted_diagram: corruptedDiagram,
			error_message: errorMessage
		})
	});

	if (!response.ok) {
		const errorText = await response.text();
		throw new Error(`Failed to fix diagram: ${errorText || response.statusText}`);
	}

	return await response.json();
}

export async function updateDiagram(rootPath: string, sectionId: string, mermaidCode: string) {
	const response = await fetch(`${API_BASE}/updateDiagram`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			root_path: rootPath,
			section_id: sectionId,
			mermaid_code: mermaidCode
		})
	});

	if (!response.ok) {
		const errorText = await response.text();
		throw new Error(`Failed to update diagram: ${errorText || response.statusText}`);
	}

	return await response.json();
}

export async function queryWikiProblem(rootPath: string, prompt: string, language?: string) {
	const response = await fetch(`${API_BASE}/wikiProblem`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			root_path: rootPath,
			prompt: prompt,
			language: language || 'en'
		})
	});

	if (!response.ok) {
		throw new Error(`Failed to query: ${response.statusText}`);
	}

	return await response.json();
}

export function queryWikiProblemStream(
	rootPath: string,
	prompt: string,
	onChunk: (chunk: string) => void,
	onComplete: (fullResponse: any) => void,
	onError: (error: string) => void,
	language?: string
): () => void {
	const wsUrl = API_BASE.replace('http', 'ws') + '/ws/wikiProblem';
	const ws = new WebSocket(wsUrl);
	
	let accumulated = '';
	
	ws.onopen = () => {
		ws.send(JSON.stringify({
			root_path: rootPath,
			prompt: prompt,
			wiki_items: null,
			language: language || 'en'
		}));
	};
	
	ws.onmessage = (event) => {
		const data = JSON.parse(event.data);
		
		if (data.type === 'chunk') {
			accumulated += data.content;
			onChunk(data.content);
		} else if (data.type === 'complete') {
			try {
				const parsed = JSON.parse(accumulated);
				onComplete(parsed);
			} catch (e) {
				onError('Failed to parse response: ' + accumulated);
			}
		} else if (data.type === 'error') {
			onError(data.message);
		}
	};
	
	ws.onerror = () => {
		onError('WebSocket connection error');
	};
	
	ws.onclose = () => {
		// Connection closed
	};
	
	// Return cleanup function
	return () => {
		if (ws.readyState === WebSocket.OPEN) {
			ws.close();
		}
	};
}


export async function queryWithWiki(rootPath: string, query: string, includeWiki: boolean = true) {
	const params = new URLSearchParams({
		root_path: rootPath,
		query: query,
		include_wiki: includeWiki.toString()
	});

	const response = await fetch(`${API_BASE}/query?${params}`, {
		method: 'POST'
	});

	if (!response.ok) {
		throw new Error(`Failed to query: ${response.statusText}`);
	}

	return await response.json();
}

export async function getDiagramReferences(rootPath: string, sectionId: string) {
	const response = await fetch(`${API_BASE}/getDiagramReferences`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			root_path: rootPath,
			section_id: sectionId
		})
	});

	if (!response.ok) {
		throw new Error(`Failed to fetch references: ${response.statusText}`);
	}

	return await response.json();
}

export async function healthCheck() {
	try {
		const response = await fetch(`${API_BASE}/health`);
		return response.ok;
	} catch {
		return false;
	}
}
