/**
 * Site-wide settings. Imported by vite.config.ts too, so keep it free of browser APIs.
 */
export const config = {
  siteName: 'Forever DB',
  /**
   * Icons are linked from a public icon host (they are not part of the repo). Swap this one function to self-host
   * later; the CSP in vite.config.ts follows it automatically.
   */
  iconUrl: (name: string, size: 'small' | 'medium' | 'large' = 'medium'): string =>
    `https://wow.zamimg.com/images/wow/icons/${size}/${name}.jpg`,
  /** Where the generated JSON lives, relative to the page (see ../pipeline/site_data.py). */
  dataPath: 'data/',
  /** Rows shown per page of the browse tables are virtualised; this is the row height in px. */
  rowHeight: 40,
};
