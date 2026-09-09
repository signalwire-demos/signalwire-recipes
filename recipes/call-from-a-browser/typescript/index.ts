// Call from a browser with the SignalWire Browser SDK v4.
// The page asks our server for a Subscriber Access Token (python/app.py: POST
// /token), connects, and dials a phone number or a Resource address. The
// project API token never leaves the server.
import { SignalWire, StaticCredentialProvider } from "@signalwire/js";

const params = new URLSearchParams(location.search);
const TO = params.get("to") ?? "/public/support"; // or a phone number: "+15551234567"

async function placeCall(status: HTMLElement): Promise<void> {
  const res = await fetch("/token", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ user: "demo-user", to: TO }),
  });
  const { token, destination } = (await res.json()) as {
    token: string;
    destination: string;
  };

  const client = new SignalWire(new StaticCredentialProvider({ token }));
  await client.connect();

  // Audio-only call to a phone number or a Fabric address such as /public/support.
  const call = await client.dial(destination, { audio: true, video: false });

  const audio = document.createElement("audio");
  audio.autoplay = true;
  document.body.appendChild(audio);
  call.remoteStream$.subscribe((stream: MediaStream | undefined) => {
    if (stream) audio.srcObject = stream;
  });
  call.status$.subscribe((state) => {
    status.textContent = `${destination}: ${state}`; // 'ringing', 'connected', ...
  });

  document.getElementById("mute")?.addEventListener("click", () => {
    void call.self?.toggleMute(); // self is null until the call is connected
  });
  document.getElementById("hangup")?.addEventListener("click", () => {
    void call.hangup();
  });
}

placeCall(document.getElementById("status")!).catch((err) =>
  console.error("call failed", err),
);
