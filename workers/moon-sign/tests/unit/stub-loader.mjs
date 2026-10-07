// Node module-loader hook: resolves the WASM package to a deterministic stub so
// the real Worker entry point (src/index.ts) can run in plain Node.
export async function resolve(specifier, context, nextResolve) {
  if (specifier === "@fusionstrings/panchangam/browser") {
    return { url: new URL("./panchangam-stub.mjs", import.meta.url).href, shortCircuit: true };
  }
  return nextResolve(specifier, context);
}
