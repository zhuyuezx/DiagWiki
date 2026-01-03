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

export async function identifyDiagramSections(rootPath: string) {
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
			language: 'en'
		})
	});

	if (!response.ok) {
		throw new Error(`Failed to identify sections: ${response.statusText}`);
	}

	return await response.json();
}

export async function generateSectionDiagram(rootPath: string, section: any, referenceFiles?: string[]) {
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
			language: 'en',
			reference_files: referenceFiles
		})
	});

	if (!response.ok) {
		throw new Error(`Failed to generate diagram: ${response.statusText}`);
	}

	return await response.json();
}

export async function queryWikiProblem(rootPath: string, prompt: string) {
	const response = await fetch(`${API_BASE}/wikiProblem`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			root_path: rootPath,
			prompt: prompt
		})
	});

	if (!response.ok) {
		throw new Error(`Failed to query: ${response.statusText}`);
	}

	return await response.json();
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
