// Despertador de Nito: el cron de Cloudflare (puntual) dispara el workflow de
// GitHub Actions cada 15 minutos, porque los crons de GitHub en cuentas nuevas
// no arrancan. Necesita el secreto GH_TOKEN (token de GitHub con scope repo+workflow).
export default {
  // La web estática pasa directa a los assets (igual que antes).
  async fetch(request, env) {
    return env.ASSETS.fetch(request);
  },

  async scheduled(event, env, ctx) {
    const res = await fetch(
      "https://api.github.com/repos/yisusxdcarmonaquevedo-cmd/nito/actions/workflows/cazador.yml/dispatches",
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${env.GH_TOKEN}`,
          "Accept": "application/vnd.github+json",
          "User-Agent": "nito-cron",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ref: "main" }),
      }
    );
    console.log(`nito-cron: dispatch -> ${res.status}`);
  },
};
