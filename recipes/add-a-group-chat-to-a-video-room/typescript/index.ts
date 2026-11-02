// Add a group chat to a video room, from the browser with Browser SDK v4.
// The page asks our server for a Subscriber Access Token (python/app.py:
// POST /token) and dials the room with audio and video. In a room call,
// call.address is the room's address: sendText() posts to the room's one
// thread, and textMessages$ is that thread, with paging for older messages.
import { SignalWire, StaticCredentialProvider } from "@signalwire/js";

const params = new URLSearchParams(location.search);
const ROOM = params.get("room") ?? "team-standup";
// in a real app the server reads the user from its session; the query string
// is how this page is opened twice as two people
const USER = params.get("user") ?? "dana@example.test";
const NAME = params.get("name") ?? "Dana";

// the fields this page renders from a message in the thread
type ChatLine = { id: string; text: string };

function isChatLine(m: unknown): m is ChatLine {
  const x = m as Partial<ChatLine> | null;
  return !!x && typeof x.id === "string" && typeof x.text === "string";
}

function render(list: HTMLElement, messages: unknown[]): void {
  list.replaceChildren();
  for (const m of messages.filter(isChatLine)) {
    const li = document.createElement("li");
    li.textContent = m.text;
    list.appendChild(li);
  }
}

async function join(root: HTMLElement): Promise<void> {
  const res = await fetch("/token", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ user: USER, display_name: NAME, room: ROOM }),
  });
  const { token, destination } = (await res.json()) as {
    token: string;
    destination: string;
  };

  const client = new SignalWire(new StaticCredentialProvider({ token }));
  await client.connect();

  // destination is "/public/<room>"; audio + video makes this a video join
  const call = await client.dial(destination, { audio: true, video: true });

  const video = document.createElement("video");
  video.autoplay = true;
  video.playsInline = true;
  root.appendChild(video);
  call.remoteStream$.subscribe((stream: MediaStream | undefined) => {
    if (stream) video.srcObject = stream;
  });

  const list = document.getElementById("chat-log") as HTMLElement;
  const input = document.getElementById("chat-input") as HTMLInputElement;
  const send = document.getElementById("chat-send") as HTMLButtonElement;

  // The room's address arrives once the call is up. It is the same address
  // for everyone in the room, so its thread is the room's group chat.
  call.address$.subscribe((address) => {
    if (!address) return;

    address.textMessages$.subscribe((thread) => {
      if (!thread) return;
      thread.values$.subscribe((messages: unknown[]) => render(list, messages));
      // older pages exist while hasMore$ is true; fetch one when the reader
      // scrolls to the top of the log
      thread.hasMore$.subscribe((more: boolean) => {
        list.dataset.more = String(more);
      });
      list.onscroll = () => {
        if (list.scrollTop === 0 && list.dataset.more === "true") thread.loadMore();
      };
    });

    send.onclick = async () => {
      const text = input.value.trim();
      if (!text) return;
      await address.sendText(text); // resolves when the platform accepts it
      input.value = "";
    };
  });

  document.getElementById("leave")?.addEventListener("click", () => {
    void call.hangup();
  });
}

join(document.getElementById("room")!).catch((err) =>
  console.error("join failed", err),
);
