window.catalogueImages = (() => {
  const basePath = "/static/images/products/";
  const fallback = `${basePath}fallback.svg`;
  let manifest = {};

  function validEntry(entry) {
    return entry && typeof entry === "object"
      && /^[A-Za-z0-9][A-Za-z0-9._-]*\.(?:jpe?g|png|webp)$/i.test(entry.filename || "")
      && ["source_page", "image_url", "license"].every(key => typeof entry[key] === "string" && entry[key].trim());
  }

  async function load() {
    try {
      const response = await fetch(`${basePath}manifest.json`, { cache: "no-cache" });
      const data = response.ok ? await response.json() : {};
      manifest = data && typeof data === "object" ? data : {};
    } catch (_) {
      manifest = {};
    }
  }

  function sourceFor(product) {
    if (product.image_url) return product.image_url;
    return localFor(product.sku);
  }

  function localFor(sku) {
    const entry = manifest[sku];
    return validEntry(entry) ? `${basePath}${encodeURIComponent(entry.filename)}` : fallback;
  }

  function recover(image, encodedSku) {
    const local = localFor(decodeURIComponent(encodedSku));
    if (image.src.endsWith(local) || local === fallback) {
      image.onerror = null;
      image.src = fallback;
      return;
    }
    image.onerror = () => {
      image.onerror = null;
      image.src = fallback;
    };
    image.src = local;
  }

  return { fallback, load, sourceFor, recover };
})();
