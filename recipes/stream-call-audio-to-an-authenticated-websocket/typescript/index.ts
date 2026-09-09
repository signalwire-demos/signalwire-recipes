/**
 * Stream call audio to a WebSocket that checks a bearer token.
 *
 * `calling.stream` opens a WebSocket to your endpoint and sends the call's
 * audio down it. The spec requires `wss://`, so plain `ws://` is refused here
 * before it is sent. `authorization_bearer_token` becomes the
 * `Authorization: Bearer` header on the connection, `track` picks which side of
 * the call to send, and `custom_parameters` reach your endpoint as connection
 * metadata. `calling.stream.stop` ends it by control id.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient.calling).
 *
 *     npm start start <call_id> wss://media.example.com/calls
 *     npm start stop <call_id>
 */
import "dotenv/config";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

// one id names this stream, and stop names it again
export const CONTROL_ID = "support-audio";

// the token your endpoint checks on the upgrade request
export const STREAM_TOKEN = process.env["STREAM_BEARER_TOKEN"] ?? "";

// the spec's three tracks
export const TRACKS = ["inbound_track", "outbound_track", "both_tracks"] as const;
export type Track = (typeof TRACKS)[number];

/** Open the stream. Returns whatever the platform says about the command. */
export function start(callId: string, url: string, track: Track = "both_tracks",
                      controlId = CONTROL_ID, statusUrl?: string, tag?: string) {
  if (!url.startsWith("wss://")) {
    // the spec: TLS is required, and plain ws:// is rejected
    throw new Error(`stream url must start with wss://, not '${url}'`);
  }
  if (!TRACKS.includes(track)) {
    throw new Error(`track must be one of ${TRACKS.join(", ")}, not '${track}'`);
  }
  const params: Record<string, unknown> = {
    control_id: controlId, url, track, codec: "PCMU", name: "support",
  };
  if (STREAM_TOKEN) {
    // arrives at your endpoint as Authorization: Bearer <token>
    params["authorization_bearer_token"] = STREAM_TOKEN;
  }
  if (tag) {
    // your own metadata, handed to the endpoint when it connects
    params["custom_parameters"] = { tag };
  }
  if (statusUrl) {
    params["status_url"] = statusUrl;
    params["status_url_method"] = "POST";
  }
  return client.calling.stream(callId, params);
}

/** End the stream. The call carries on. */
export function stop(callId: string, controlId = CONTROL_ID) {
  return client.calling.streamStop(callId, { control_id: controlId });
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd, callId, url] = process.argv.slice(2);
  if (!callId) {
    console.log("usage: npm start <start|stop> <call_id> [wss url]");
  } else if (cmd === "start") {
    console.log(await start(callId, url));
  } else if (cmd === "stop") {
    console.log(await stop(callId));
  }
}
