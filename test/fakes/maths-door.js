/* The maths library door's fake (architecture.md, Library doors; library_fakes.py): obsMaths's
   calls answered without math.js. Complex numbers are plain {re, im} objects with the door's
   operations in principal branches, and a small parser reads numbers, names, calls, + - * / ^,
   unary signs, parentheses and implicit multiplication into the door's syntax tree;
   test_library_doors_browser.py holds it to the door's contract. */
globalThis.obsMaths = (() => {
  const complex = (re, im = 0) => ({re, im});
  const add = (a, b) => complex(a.re + b.re, a.im + b.im);
  const sub = (a, b) => complex(a.re - b.re, a.im - b.im);
  const mul = (a, b) => complex(a.re * b.re - a.im * b.im, a.re * b.im + a.im * b.re);
  const div = (a, b) => {
    const d = b.re * b.re + b.im * b.im;
    return complex((a.re * b.re + a.im * b.im) / d, (a.im * b.re - a.re * b.im) / d);
  };
  const exp = a => complex(Math.exp(a.re) * Math.cos(a.im), Math.exp(a.re) * Math.sin(a.im));
  const log = a => complex(Math.log(Math.hypot(a.re, a.im)), Math.atan2(a.im, a.re));
  const sqrt = a => (a.re === 0 && a.im === 0 ? complex(0) : exp(mul(complex(0.5), log(a))));
  const I = complex(0, 1);
  const pow = (a, b) => {
    if (a.re === 0 && a.im === 0) return b.re === 0 && b.im === 0 ? complex(1) : b.re > 0 ? complex(0) : complex(NaN, NaN);
    if (a.im === 0 && b.im === 0 && a.re > 0) return complex(Math.pow(a.re, b.re));
    return exp(mul(b, log(a)));
  };
  const sin = a => complex(Math.sin(a.re) * Math.cosh(a.im), Math.cos(a.re) * Math.sinh(a.im));
  const cos = a => complex(Math.cos(a.re) * Math.cosh(a.im), -Math.sin(a.re) * Math.sinh(a.im));
  const sinh = a => complex(Math.sinh(a.re) * Math.cos(a.im), Math.cosh(a.re) * Math.sin(a.im));
  const cosh = a => complex(Math.cosh(a.re) * Math.cos(a.im), Math.sinh(a.re) * Math.sin(a.im));
  // asin z = -i log(iz + sqrt(1 - z^2)); acos z = pi/2 - asin z; atan z = (i/2) log((i + z) / (i - z)).
  const asin = a => mul(complex(0, -1), log(add(mul(I, a), sqrt(sub(complex(1), mul(a, a))))));
  const operations = {
    add, mul, pow, exp, log, sin, cos, tan: a => div(sin(a), cos(a)),
    asin, acos: a => sub(complex(Math.PI / 2), asin(a)),
    atan: a => mul(complex(0, 0.5), log(div(add(I, a), sub(I, a)))),
    sinh, cosh, tanh: a => div(sinh(a), cosh(a)),
    abs: a => Math.hypot(a.re, a.im),
  };
  const BINARY = {"+": "add", "-": "subtract", "*": "multiply", "/": "divide"};
  function parse(text) {
    const tokens = [];
    const pattern = /\s*(?:(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)|([A-Za-z_][A-Za-z0-9_]*)|([-+*/^(),]))/y;
    let index = 0;
    while (index < text.length) {
      if (/^\s*$/.test(text.slice(index))) break;
      pattern.lastIndex = index;
      const match = pattern.exec(text);
      if (!match) throw new Error(`Unexpected character "${text.trim()[0] ?? ""}" (char ${index + 1})`);
      tokens.push(match[1] !== undefined ? {number: Number(match[1])} : match[2] !== undefined ? {name: match[2]} : {symbol: match[3]});
      index = pattern.lastIndex;
    }
    let at = 0;
    const peek = () => tokens[at];
    const take = symbol => (peek()?.symbol === symbol ? (at += 1, true) : false);
    const fail = () => { throw new Error(at < tokens.length ? `Unexpected token (token ${at + 1})` : "Unexpected end of expression"); };
    function primary() {
      const token = peek();
      if (!token) fail();
      if ("number" in token) { at += 1; return {number: token.number}; }
      if ("name" in token) {
        at += 1;
        if (!take("(")) return {name: token.name};
        const args = [];
        if (!take(")")) {
          do args.push(sum()); while (take(","));
          if (!take(")")) fail();
        }
        return {call: token.name, args};
      }
      if (take("(")) {
        const inner = sum();
        if (!take(")")) fail();
        return inner;
      }
      return fail();
    }
    function power() {
      const base = primary();
      return take("^") ? {operator: "pow", symbol: "^", args: [base, unary()]} : base;
    }
    function unary() {
      if (take("-")) return {operator: "unaryMinus", symbol: "-", args: [unary()]};
      if (take("+")) return {operator: "unaryPlus", symbol: "+", args: [unary()]};
      return power();
    }
    function product() {
      let left = unary();
      for (;;) {
        const token = peek();
        if (token?.symbol === "*" || token?.symbol === "/") {
          at += 1;
          left = {operator: BINARY[token.symbol], symbol: token.symbol, args: [left, unary()]};
        } else if (token && ("number" in token || "name" in token || token.symbol === "(")) {
          left = {operator: "multiply", symbol: "*", args: [left, power()]};
        } else return left;
      }
    }
    function sum() {
      let left = product();
      for (;;) {
        const token = peek();
        if (token?.symbol !== "+" && token?.symbol !== "-") return left;
        at += 1;
        left = {operator: BINARY[token.symbol], symbol: token.symbol, args: [left, product()]};
      }
    }
    const tree = sum();
    if (at < tokens.length) fail();
    return tree;
  }
  return {available: () => true, complex, operations, parse};
})();
