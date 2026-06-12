'use strict';

// Template engine — Jinja2 subset: {{ var }}, {% if expr %}...{% else %}...{% endif %}
// Expression grammar matches expression-evaluator.ts (wizard system).

var EXPR_STOP = {'&':1, '|':1, '!':1, '=':1, '(':1, ')':1, "'":1, ' ':1, '\t':1};

function evaluateExpr(expr, context) {
  var pos = 0;
  function skipWs() { while (pos < expr.length && (expr[pos] === ' ' || expr[pos] === '\t')) pos++; }
  function peek(s) { return expr.substr(pos, s.length) === s; }
  function consume(s) { if (!peek(s)) throw new Error('Expected "' + s + '" at pos ' + pos + ' in: ' + expr); pos += s.length; }
  function toBool(v) { return v !== false && v !== null && v !== undefined && v !== ''; }

  function orExpr() {
    var r = andExpr();
    while (pos < expr.length) { skipWs(); if (peek('||')) { consume('||'); skipWs(); var right = andExpr(); r = toBool(r) || toBool(right); } else break; }
    return r;
  }
  function andExpr() {
    var r = notExpr();
    while (pos < expr.length) { skipWs(); if (peek('&&')) { consume('&&'); skipWs(); var right = notExpr(); r = toBool(r) && toBool(right); } else break; }
    return r;
  }
  function notExpr() {
    skipWs();
    if (pos < expr.length && expr[pos] === '!' && !peek('!=')) { pos++; skipWs(); return !toBool(notExpr()); }
    return compare();
  }
  function compare() {
    var left = primary();
    skipWs();
    if (peek('==')) { consume('=='); skipWs(); return left === primary(); }
    if (peek('!=')) { consume('!='); skipWs(); return left !== primary(); }
    return toBool(left);
  }
  function primary() {
    skipWs();
    if (pos >= expr.length) throw new Error('Unexpected end of expression: ' + expr);
    if (expr[pos] === '(') { pos++; skipWs(); var r = orExpr(); skipWs(); consume(')'); return r; }
    if (expr[pos] === "'") { consume("'"); var s = pos; var e = expr.indexOf("'", s); if (e === -1) throw new Error('Unterminated string in: ' + expr); pos = e + 1; return expr.substring(s, e); }
    if (peek('true') && (pos + 4 >= expr.length || EXPR_STOP[expr[pos + 4]])) { pos += 4; return true; }
    if (peek('false') && (pos + 5 >= expr.length || EXPR_STOP[expr[pos + 5]])) { pos += 5; return false; }
    var start = pos;
    while (pos < expr.length && !EXPR_STOP[expr[pos]]) pos++;
    var ref = expr.substring(start, pos);
    if (!ref) throw new Error('Expected field reference at pos ' + start + ' in: ' + expr);
    var val = context[ref];
    return (val === undefined || val === null) ? false : val;
  }

  skipWs();
  var result = orExpr();
  skipWs();
  if (pos < expr.length) throw new Error('Unexpected "' + expr[pos] + '" at pos ' + pos + ' in: ' + expr);
  return toBool(result);
}

function findIfBlock(template, startPos) {
  var depth = 1;
  var pos = startPos;
  var ifBodyEnd = -1;
  var elseStart = -1;

  while (pos < template.length) {
    var nextTag = template.indexOf('{%', pos);
    if (nextTag === -1) throw new Error('Unclosed {% if %}');
    var tagClose = template.indexOf('%}', nextTag);
    if (tagClose === -1) throw new Error('Unclosed {% tag');
    var tag = template.substring(nextTag + 2, tagClose).trim();
    var afterTag = tagClose + 2;

    if (tag.indexOf('if ') === 0) {
      depth++;
    } else if (tag === 'endif') {
      depth--;
      if (depth === 0) {
        return {
          ifBody: template.substring(startPos, ifBodyEnd === -1 ? nextTag : ifBodyEnd),
          elseBody: elseStart === -1 ? null : template.substring(elseStart, nextTag),
          endPos: afterTag
        };
      }
    } else if (tag === 'else' && depth === 1) {
      ifBodyEnd = nextTag;
      elseStart = afterTag;
    }
    pos = afterTag;
  }
  throw new Error('Unclosed {% if %}');
}

function render(template, context) {
  var result = '';
  var pos = 0;

  while (pos < template.length) {
    var tagStart = template.indexOf('{%', pos);
    if (tagStart === -1) {
      result += template.substring(pos);
      break;
    }
    result += template.substring(pos, tagStart);
    var tagClose = template.indexOf('%}', tagStart);
    if (tagClose === -1) throw new Error('Unclosed {% tag');
    var tag = template.substring(tagStart + 2, tagClose).trim();
    pos = tagClose + 2;

    if (tag.indexOf('if ') === 0) {
      var expr = tag.substring(3).trim();
      var block = findIfBlock(template, pos);
      if (evaluateExpr(expr, context)) {
        result += render(block.ifBody, context);
      } else if (block.elseBody !== null) {
        result += render(block.elseBody, context);
      }
      pos = block.endPos;
    } else {
      throw new Error('Unknown template tag: {% ' + tag + ' %}');
    }
  }

  result = result.replace(/\{\{\s*([^}]+?)\s*\}\}/g, function(match, varName) {
    var val = context[varName.trim()];
    return (val !== null && val !== undefined) ? String(val) : '';
  });

  return result;
}

function splitCells(template) {
  var cells = [];
  var pos = 0;
  var cellStart = 0;

  while (pos < template.length) {
    if (template[pos] === '{' && pos + 1 < template.length) {
      var next = template[pos + 1];
      if (next === '%') {
        var end = template.indexOf('%}', pos + 2);
        if (end === -1) throw new Error('Unclosed {% tag');
        pos = end + 2;
        continue;
      }
      if (next === '{') {
        var end = template.indexOf('}}', pos + 2);
        if (end === -1) throw new Error('Unclosed {{ tag');
        pos = end + 2;
        continue;
      }
    }
    if (template[pos] === '|') {
      cells.push(template.substring(cellStart, pos));
      cellStart = pos + 1;
    }
    pos++;
  }
  cells.push(template.substring(cellStart));
  return cells;
}

module.exports = { render: render, splitCells: splitCells };
