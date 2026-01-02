/**
 * Retry utility for diagram generation with exponential backoff
 */

export const RETRY_MAX = 3;
export const RETRY_DELAY_MS = 2000;

/**
 * Execute a function with automatic retry logic
 * @param fn - The async function to retry
 * @param context - Context for logging (e.g., section_id)
 * @returns The result of the function
 * @throws The last error if all retries fail
 */
export async function retryWithBackoff<T>(
	fn: () => Promise<T>,
	context: string
): Promise<T> {
	let lastError: Error | null = null;

	for (let attempt = 1; attempt <= RETRY_MAX; attempt++) {
		try {
			console.log(`[${context}] Attempt ${attempt}/${RETRY_MAX}...`);
			const result = await fn();
			console.log(`[${context}] Success on attempt ${attempt}`);
			return result;
		} catch (err) {
			lastError = err instanceof Error ? err : new Error(String(err));
			console.warn(`[${context}] Attempt ${attempt} failed: ${lastError.message}`);

			if (attempt < RETRY_MAX) {
				console.log(`[${context}] Retrying in ${RETRY_DELAY_MS}ms...`);
				await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
			}
		}
	}

	throw lastError || new Error('All retry attempts failed');
}
