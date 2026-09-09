// Receive calls in the browser with the SignalWire Browser SDK (v3).
// The page takes the subscriber token that `python app.py token` printed,
// registers with `client.online`, and answers the next call into <div id="call">.
// The project API token never reaches the page; only the per-person token does.
import { SignalWire } from "@signalwire/js";

// The SDK's IncomingCallNotification type is not exported from the package
// root, so this is the slice of `notification.invite` the page uses. The
// assignment below is checked against the SDK's own type: no cast.
type Invite = {
  details: { callID: string };
  accept: (opts: { rootElement: HTMLElement }) => Promise<unknown>;
  reject: () => Promise<unknown>;
};

let pending: Invite | null = null;

async function goOnline(token: string, status: HTMLElement): Promise<void> {
  const client = await SignalWire({ token });

  // Register for incoming calls. `all` runs for every call to this subscriber's
  // address; the notification carries the invite to accept or reject.
  await client.online({
    incomingCallHandlers: {
      all: (notification) => {
        pending = notification.invite;
        status.textContent = `ringing: ${pending.details.callID}`;
      },
    },
  });
  status.textContent = "online, waiting for a call";
}

async function answer(status: HTMLElement): Promise<void> {
  if (!pending) return;
  const root = document.getElementById("call")!;
  await pending.accept({ rootElement: root }); // media renders into the element
  status.textContent = `connected: ${pending.details.callID}`;
  pending = null;
}

async function decline(status: HTMLElement): Promise<void> {
  if (!pending) return;
  await pending.reject();
  status.textContent = "declined";
  pending = null;
}

const status = document.getElementById("status")!;
const tokenField = document.getElementById("token") as HTMLInputElement;
document.getElementById("online")?.addEventListener("click", () => {
  goOnline(tokenField.value.trim(), status).catch((err) =>
    console.error("online failed", err),
  );
});
document.getElementById("answer")?.addEventListener("click", () => {
  void answer(status);
});
document.getElementById("decline")?.addEventListener("click", () => {
  void decline(status);
});
