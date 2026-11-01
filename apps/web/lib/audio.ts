// Turn a browser recording into the WAV file the back end expects.
// Phones record in different formats (webm, mp4...). Converting here means the server
// only ever has to read one simple format.

const SAMPLE_RATE = 16_000; // the rate the cough model was trained on

/** Decode a recording, mix it to one channel at 16 kHz and wrap it as a WAV file. */
export async function recordingToWav(recording: Blob): Promise<Blob> {
  const context = new AudioContext();
  try {
    const decoded = await context.decodeAudioData(await recording.arrayBuffer());
    const frames = Math.ceil(decoded.duration * SAMPLE_RATE);
    const offline = new OfflineAudioContext(1, frames, SAMPLE_RATE);
    const source = offline.createBufferSource();
    source.buffer = decoded;
    source.connect(offline.destination);
    source.start();
    const rendered = await offline.startRendering();
    return encodeWav(rendered.getChannelData(0));
  } finally {
    await context.close();
  }
}

/** A WAV file is a 44-byte header followed by the sound as 16-bit numbers. */
function encodeWav(samples: Float32Array): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeText = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };
  writeText(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true); // size of this header section
  view.setUint16(20, 1, true); // 1 = plain uncompressed sound
  view.setUint16(22, 1, true); // one channel
  view.setUint32(24, SAMPLE_RATE, true);
  view.setUint32(28, SAMPLE_RATE * 2, true); // bytes per second
  view.setUint16(32, 2, true); // bytes per sample
  view.setUint16(34, 16, true); // bits per sample
  writeText(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, i) => {
    const clipped = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + i * 2, clipped * 0x7fff, true);
  });
  return new Blob([buffer], { type: "audio/wav" });
}
