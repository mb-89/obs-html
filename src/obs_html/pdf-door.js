/* The PDF library's door (architecture.md, Library doors): the one script that calls pdf-lib.
   Attach source ZIP to PDF (archive.js) reads and writes a PDF through it; the library is embedded
   before it (libraries.py). */
globalThis.obsPdf = (() => {
  const library = () => globalThis.PDFLib;
  /* Whether the loaded document holds an embedded file named `filename`, in its name tree. */
  function holds(pdf, filename) {
    const {PDFName, PDFDict, PDFArray} = library();
    const names = pdf.catalog.lookupMaybe(PDFName.of("Names"), PDFDict);
    const files = names?.lookupMaybe(PDFName.of("EmbeddedFiles"), PDFDict);
    const hasName = (tree) => {
      const entries = tree.lookupMaybe(PDFName.of("Names"), PDFArray);
      if (entries) {
        for (let index = 0; index < entries.size(); index += 2) {
          if (entries.lookup(index).decodeText() === filename) return true;
        }
      }
      const children = tree.lookupMaybe(PDFName.of("Kids"), PDFArray);
      return children ? children.asArray().some(child => hasName(pdf.context.lookup(child, PDFDict))) : false;
    };
    return Boolean(files && hasName(files));
  }
  const signed = pdf => pdf.catalog.has(library().PDFName.of("Perms")) ||
    pdf.getForm().getFields().some(field => field instanceof library().PDFSignature);
  return {
    /* Whether the library loaded. */
    available: () => Boolean(library()),
    /* Whether the PDF `source` (bytes) holds an attachment named `filename`. */
    async attached(source, filename) {
      return holds(await library().PDFDocument.load(source), filename);
    },
    /* The PDF `source` (bytes) with `file` (bytes) attached as `filename`, its source document
       (the attachment's relationship Source), as bytes. Throws an Error for a signed PDF, which
       an attachment would invalidate, and for a PDF that already holds `filename`. */
    async attach(source, file, {filename, mimeType, description}) {
      const pdf = await library().PDFDocument.load(source);
      if (signed(pdf)) throw new Error("Signed PDFs cannot be modified; attach the ZIP before signing.");
      if (holds(pdf, filename)) throw new Error(`PDF already contains ${filename}; choose the PDF as printed.`);
      await pdf.attach(file, filename, {mimeType, description, afRelationship: library().AFRelationship.Source});
      return pdf.save();
    },
  };
})();
