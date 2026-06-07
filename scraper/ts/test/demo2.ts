export const a = () => {};

export function sortStringsAscending(data: string[]): string[] {
  return data.sort((a, b) => a.localeCompare(b));
}
