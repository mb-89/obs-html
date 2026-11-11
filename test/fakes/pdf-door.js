/* The PDF library door's fake (architecture.md, Library doors; library_fakes.py): obsPdf's calls
   answered without pdf-lib. An attachment is a comment line after the PDF's end, which the fake
   finds again by its name; a PDF whose bytes name a /Perms dictionary or a signature field is
   signed. test_library_doors_browser.py holds it to the door's contract. */
globalThis.obsPdf = (() => {
  const text = bytes => Array.from(new Uint8Array(bytes), byte => String.fromCharCode(byte)).join("");
  const marker = filename => `\n%obs-fake-attachment ${encodeURIComponent(filename)}\n`;
  const pdf = source => {
    const content = text(source);
    if (!content.startsWith("%PDF-")) throw new Error("Failed to parse PDF document: no PDF header");
    return content;
  };
  return {
    available: () => true,
    async attached(source, filename) {
      return pdf(source).includes(marker(filename));
    },
    async attach(source, file, {filename}) {
      const content = pdf(source);
      if (/\/Perms\b|\/FT\s*\/Sig\b/.test(content)) {
        throw new Error("Signed PDFs cannot be modified; attach the ZIP before signing.");
      }
      if (content.includes(marker(filename))) throw new Error(`PDF already contains ${filename}; choose the PDF as printed.`);
      const tail = new TextEncoder().encode(marker(filename));
      const result = new Uint8Array(source.byteLength + tail.length + new Uint8Array(file).length);
      result.set(new Uint8Array(source), 0);
      result.set(tail, source.byteLength);
      result.set(new Uint8Array(file), source.byteLength + tail.length);
      return result;
    },
  };
})();
