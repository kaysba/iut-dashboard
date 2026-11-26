/* État partagé de l'interface (remplace window.__me et window.__webmail).
   me : réponse de /api/me ; webmail : adresse d'Outlook sur le web, connue après la lecture des mails. */
export const state = { me: null, webmail: null };
