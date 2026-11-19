// The workshop key is typed by the user and kept only for the browser session (sessionStorage); it is never bundled in the page.
const STORAGE_KEY = "smartcar-workshop-key";

export function getWriteKey(): string {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setWriteKey(value: string): void {
  try {
    if (value) window.sessionStorage.setItem(STORAGE_KEY, value);
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage blocked: the key is simply asked again */
  }
}
