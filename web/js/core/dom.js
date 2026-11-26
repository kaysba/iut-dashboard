/* Accès au DOM, échappement HTML et icônes. */

export const $ = (s, el = document) => el.querySelector(s);
export const main = $("#main");
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export const ICON = {
  close: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  ext: '<svg viewBox="0 0 24 24"><path d="M13.5 5.5H18.5V10.5M18 6l-7.5 7.5M16 13.5V18a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 18V9.5A1.5 1.5 0 0 1 6 8h4.5"/></svg>',
  dl: '<svg viewBox="0 0 24 24"><path d="M12 4.5v10M7.5 10.5 12 15l4.5-4.5M5 19.5h14"/></svg>',
  clip: '<svg viewBox="0 0 24 24"><path d="m19 11.5-6.8 6.8a4.2 4.2 0 0 1-6-6l7.2-7.1a2.8 2.8 0 0 1 4 4l-7.1 7.1a1.4 1.4 0 0 1-2-2l6.4-6.4"/></svg>',
  search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg>',
  left: '<svg viewBox="0 0 24 24"><path d="m14.5 6-6 6 6 6"/></svg>',
  right: '<svg viewBox="0 0 24 24"><path d="m9.5 6 6 6-6 6"/></svg>',
  link: '<svg viewBox="0 0 24 24"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></svg>',
  folder: '<svg viewBox="0 0 24 24"><path d="M3.5 7a1.5 1.5 0 0 1 1.5-1.5h4.2l2 2.2H19a1.5 1.5 0 0 1 1.5 1.5v8.3A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5z"/></svg>',
  page: '<svg viewBox="0 0 24 24"><path d="M7 3.5h7l4.5 4.5v12.5H7z"/><path d="M13.5 3.5V8.5H18.5M10 12.5h5.5M10 16h5.5"/></svg>',
  assign: '<svg viewBox="0 0 24 24"><path d="M12 15V4.5M7.5 9 12 4.5 16.5 9M5 15.5v3a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3"/></svg>',
  quiz: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M9.8 9.6a2.3 2.3 0 1 1 3.2 2.1c-.6.3-1 .8-1 1.5v.4M12 16.6v.1"/></svg>',
  forum: '<svg viewBox="0 0 24 24"><path d="M5 5.5h11a1.5 1.5 0 0 1 1.5 1.5v6.5A1.5 1.5 0 0 1 16 15H10l-4 3.5V15H5a1.5 1.5 0 0 1-1.5-1.5V7A1.5 1.5 0 0 1 5 5.5z"/></svg>',
  trophy: '<svg viewBox="0 0 24 24"><path d="M8 4.5h8v5a4 4 0 0 1-8 0zM8 6.5H5v1.5a3 3 0 0 0 3 3M16 6.5h3v1.5a3 3 0 0 1-3 3M12 13.5v3.5M8.5 19.5h7M10 17h4"/></svg>',
  medal: '<svg viewBox="0 0 24 24"><circle cx="12" cy="14.5" r="4.5"/><path d="m9 10.2-2.5-6h4l1.5 3M15 10.2l2.5-6h-4L12 7.5"/></svg>',
  video: '<svg viewBox="0 0 24 24"><rect x="3.5" y="6" width="12" height="12" rx="2"/><path d="m15.5 10.5 5-3v9l-5-3"/></svg>',
};
