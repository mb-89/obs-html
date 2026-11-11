/* The maths library's door (architecture.md, Library doors): the one script that calls math.js.
   Equation figures (equations.js) compute with its complex numbers and parse a reader's
   expressions through it; the library is embedded before it (libraries.py). */
globalThis.obsMaths = (() => {
  const library = () => globalThis.math;
  /* A math.js expression node as the door's syntax tree: {number}, {name}, {operator, args} by
     math.js's operator names ("add", "subtract", "multiply", "divide", "pow", "unaryMinus",
     "unaryPlus", ...), {call, args}, or {other} naming a node of any other kind. */
  function syntax(node) {
    if (node.type === "ParenthesisNode") return syntax(node.content);
    if (node.type === "ConstantNode") return {number: node.value};
    if (node.type === "SymbolNode") return {name: node.name};
    if (node.type === "OperatorNode") return {operator: node.fn, symbol: node.op, args: node.args.map(syntax)};
    if (node.type === "FunctionNode") return {call: node.fn.name, args: node.args.map(syntax)};
    return {other: node.type};
  }
  return {
    /* Whether the library loaded. */
    available: () => Boolean(library()?.Complex),
    /* The complex number re + im·i: an object with numbers `re` and `im`, which only this door's
       operations take. */
    complex: (re, im = 0) => new (library().Complex)(re, im),
    /* The complex operations, principal branches throughout; `abs` returns a number. */
    operations: {
      add: (a, b) => a.add(b), mul: (a, b) => a.mul(b), pow: (a, b) => a.pow(b),
      exp: a => a.exp(), log: a => a.log(),
      sin: a => a.sin(), cos: a => a.cos(), tan: a => a.tan(),
      asin: a => a.asin(), acos: a => a.acos(), atan: a => a.atan(),
      sinh: a => a.sinh(), cosh: a => a.cosh(), tanh: a => a.tanh(),
      abs: a => a.abs(),
    },
    /* A reader's expression as the door's syntax tree; throws an Error saying why it does not parse. */
    parse: text => syntax(library().parse(text)),
  };
})();
