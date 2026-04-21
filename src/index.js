export default {
  async fetch(request, env) {
    // Handle Bale webhook (or use getUpdates, but webhook is simpler)
    if (request.method === "POST") {
      const update = await request.json();
      await handleUpdate(update, env);
      return new Response("OK", { status: 200 });
    }
    return new Response("Bale YouTube Bot Worker", { status: 200 });
  }
};

async function handleUpdate(update, env) {
  const message = update.message;
  if (!message) return;
  const chatId = message.chat.id;
  const text = message.text || "";

  if (text === "/start") {
    await sendMessage(chatId, "Send me a YouTube URL. I'll prepare the download.", env);
    return;
  }

  // Extract YouTube URL
  const youtubeRegex = /(youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/;
  const match = text.match(youtubeRegex);
  if (!match) {
    await sendMessage(chatId, "Please send a valid YouTube URL.", env);
    return;
  }

  const videoUrl = text;
  await sendMessage(chatId, "⏳ Download request received. I'll notify you when it's ready (may take a few minutes).", env);

  // Trigger GitHub Action via repository_dispatch
  await triggerGitHubWorkflow(videoUrl, chatId, env);
}

async function sendMessage(chatId, text, env) {
  const url = `https://tapi.bale.ai/bot${env.BALE_BOT_TOKEN}/sendMessage`;
  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text })
  });
}

async function triggerGitHubWorkflow(videoUrl, chatId, env) {
  const apiUrl = `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`;
  await fetch(apiUrl, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Accept": "application/vnd.github.v3+json",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      event_type: "download-youtube",
      client_payload: {
        video_url: videoUrl,
        chat_id: chatId
      }
    })
  });
}
