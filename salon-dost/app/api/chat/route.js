export async function POST(request) {
  const body = await request.json();

  const response = await fetch("https://arhm4341-salon-chatbot.hf.space/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return Response.json(data);
}