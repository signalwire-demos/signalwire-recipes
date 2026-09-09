// Join the room from the browser with the SignalWire Browser SDK v4.
// The page asks our server for a Guest token (python/app.py: POST /token), then
// dials the room's Fabric address with audio and video. The token can reach
// only that address, and the project API token never leaves the server.
import { SignalWire, StaticCredentialProvider } from "@signalwire/js";

const ROOM = new URLSearchParams(location.search).get("room") ?? "team-standup";

async function joinRoom(rootElement: HTMLElement): Promise<void> {
  const res = await fetch("/token", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ room: ROOM }),
  });
  const { token, destination } = (await res.json()) as {
    token: string;
    destination: string;
  };

  const client = new SignalWire(new StaticCredentialProvider({ token }));
  await client.connect();

  // destination is "/public/<room>"; audio + video makes this a video join.
  const call = await client.dial(destination, { audio: true, video: true });

  // Render the mixed room stream (an MCU: one stream per participant).
  const video = document.createElement("video");
  video.autoplay = true;
  video.playsInline = true;
  rootElement.appendChild(video);
  call.remoteStream$.subscribe((stream: MediaStream | undefined) => {
    if (stream) video.srcObject = stream;
  });

  // Layouts and screen share are call-level controls.
  document.getElementById("layout")?.addEventListener("change", (e) => {
    // setLayout(layout, positions): e.g. "grid-responsive", "highlight-1-responsive"
    void call.setLayout((e.target as HTMLSelectElement).value, {});
  });
  document.getElementById("share")?.addEventListener("click", () => {
    void call.self?.startScreenShare(); // self is null until the call is connected
  });
  document.getElementById("leave")?.addEventListener("click", () => {
    void call.hangup();
  });
}

joinRoom(document.getElementById("room")!).catch((err) =>
  console.error("join failed", err),
);
