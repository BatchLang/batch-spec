parser grammar BatchParser;

options { tokenVocab = BatchLexer; }

@parser::members {
def _notForToken(self) -> bool:
    from BatchLexer import BatchLexer  # isort: skip
    return self._input.LA(1) != BatchLexer.FOR

def _laIf(self) -> bool:
    from BatchLexer import BatchLexer  # isort: skip
    return self._input.LA(1) == BatchLexer.IF

def _laFor(self) -> bool:
    from BatchLexer import BatchLexer  # isort: skip
    return self._input.LA(1) == BatchLexer.FOR

def _laElse(self) -> bool:
    from BatchLexer import BatchLexer  # isort: skip
    return self._input.LA(1) == BatchLexer.ELSE

def _laRem(self) -> bool:
    from BatchLexer import BatchLexer  # isort: skip
    return self._input.LA(1) == BatchLexer.REM

def _genericCmdStartOk(self) -> bool:
    # Do not let genericCmd absorb IF/FOR/ELSE/REM; those have dedicated rules
    # so invalid IF predicates surface as syntax errors (live cmd) and REM
    # remarks through EOL (including after & / && / ||).
    return not (self._laIf() or self._laFor() or self._laElse() or self._laRem())

def _redirectOnlyStatement(self) -> bool:
    # Live cmd rejects a statement that is only redirects (no command name),
    # including bash-like &>file (AMP then >file) and a lone >file.
    # Leading redirects remain valid when a command follows (>file echo hi).
    from BatchLexer import BatchLexer  # isort: skip

    redir_ops = {
        BatchLexer.GT,
        BatchLexer.LT,
        BatchLexer.APPEND,
        BatchLexer.DUP_OUT,
        BatchLexer.DUP_IN,
    }
    stop = {
        BatchLexer.NEWLINE,
        BatchLexer.AMP,
        BatchLexer.PIPE,
        BatchLexer.AMPAMP,
        BatchLexer.PIPEPIPE,
        BatchLexer.RPAREN,
        -1,
    }
    i = 1
    saw_command = False
    while True:
        tok = self._input.LA(i)
        if tok in stop:
            break
        if tok == BatchLexer.NUMBER and self._input.LA(i + 1) in redir_ops:
            i += 1
            tok = self._input.LA(i)
        if tok in (BatchLexer.GT, BatchLexer.LT, BatchLexer.APPEND):
            i += 1
            nxt = self._input.LA(i)
            if nxt in stop or nxt in redir_ops:
                return True
            i += 1
            continue
        if tok in (BatchLexer.DUP_OUT, BatchLexer.DUP_IN):
            i += 1
            nxt = self._input.LA(i)
            if nxt in stop:
                return True
            i += 1
            continue
        saw_command = True
        i += 1
    return not saw_command

def _enterGroup(self) -> None:
    self._groupDepth = getattr(self, "_groupDepth", 0) + 1

def _exitGroup(self) -> None:
    self._groupDepth = max(getattr(self, "_groupDepth", 0) - 1, 0)

def _notLonelyParen(self) -> bool:
    from BatchLexer import BatchLexer  # isort: skip
    la1 = self._input.LA(1)
    if la1 != BatchLexer.RPAREN:
        return True
    # Lonely ')' closes a paren block; do not absorb into genericCmd.
    # ELSE must be lonely so ") ELSE" builds elseClause (IF /? form).
    la2 = self._input.LA(2)
    return la2 not in (
        BatchLexer.NEWLINE,
        BatchLexer.AMP,
        BatchLexer.PIPE,
        BatchLexer.AMPAMP,
        BatchLexer.PIPEPIPE,
        BatchLexer.ELSE,
        -1,
    )

def _rparenAsTokenOk(self) -> bool:
    # Inside a parenthesized command group, unquoted ')' closes the group
    # (live cmd: leftover text after that closer is a syntax error). At
    # script level, same-line ')' can still be command text.
    from BatchLexer import BatchLexer  # isort: skip

    if self._input.LA(1) != BatchLexer.RPAREN:
        return True
    if getattr(self, "_groupDepth", 0) > 0:
        return False
    return self._notLonelyParen()

def _inlineLparenOk(self) -> bool:
    # Same-line '(' stays in command text (echo a (echo b) prints literally
    # at script level). Inside a group, unquoted ')' still closes the group
    # (see _rparenAsTokenOk). A '(' immediately before NEWLINE starts a
    # multi-line group that still runs after the preceding command (live:
    # unknowncmd ( / and ( followed by a block), except the ECHO blank-line
    # idiom echo( which is WORD echo plus a glued LPAREN with no following
    # group (expansion.yaml echo_forms.blank_line_examples).
    from BatchLexer import BatchLexer  # isort: skip

    if self._input.LA(1) != BatchLexer.LPAREN:
        return True
    if self._input.LA(2) != BatchLexer.NEWLINE:
        return True
    prev = self._input.LT(-1)
    cur = self._input.LT(1)
    if prev is None or cur is None:
        return False
    glued = not self._gapHasSpaceOrTab(prev, cur)
    if glued and (prev.text or "").lower() == "echo":
        return True
    return False

def _remTokenOk(self) -> bool:
    # REM remarks through EOL, but leave a trailing multi-line '(' for
    # statement-level groupStmt (live still runs the following block).
    from BatchLexer import BatchLexer  # isort: skip

    la1 = self._input.LA(1)
    if la1 in (BatchLexer.NEWLINE, -1):
        return False
    if la1 == BatchLexer.LPAREN and not self._inlineLparenOk():
        return False
    return True

def _setDiscardedTokenOk(self) -> bool:
    # Trailer after set "name=value" stops at chain separators, newline/EOF,
    # and redirect operators (those attach via setRedirects instead).
    from BatchLexer import BatchLexer  # isort: skip

    redir_ops = {
        BatchLexer.GT,
        BatchLexer.LT,
        BatchLexer.APPEND,
        BatchLexer.DUP_OUT,
        BatchLexer.DUP_IN,
    }
    stop = {
        BatchLexer.NEWLINE,
        BatchLexer.AMP,
        BatchLexer.PIPE,
        BatchLexer.AMPAMP,
        BatchLexer.PIPEPIPE,
        -1,
    }
    la1 = self._input.LA(1)
    if la1 in stop or la1 in redir_ops:
        return False
    if la1 == BatchLexer.NUMBER and self._input.LA(2) in redir_ops:
        return False
    return True

def _enterThenStmt(self) -> None:
    self._thenStmtDepth = getattr(self, "_thenStmtDepth", 0) + 1

def _exitThenStmt(self) -> None:
    self._thenStmtDepth = getattr(self, "_thenStmtDepth", 0) - 1

def _elseAsArgAllowed(self) -> bool:
    # Inside IF then-statement (non-paren), bare ELSE starts elseClause.
    return getattr(self, "_thenStmtDepth", 0) == 0

def _notOpenParenThen(self) -> bool:
    from BatchLexer import BatchLexer  # isort: skip
    # Same-line '(' after the predicate starts a paren block (IF /?).
    return self._input.LA(1) != BatchLexer.LPAREN

def _expandedPredicateOk(self) -> bool:
    # After %var% / %1 / !var! as a full expanded predicate, another operand
    # without a compare-op is a live syntax error (IF %ERRORLEVEL% 1).
    from BatchLexer import BatchLexer  # isort: skip
    return self._input.LA(1) not in (
        BatchLexer.NUMBER,
        BatchLexer.HEX_NUMBER,
        BatchLexer.PERCENT_VAR,
        BatchLexer.PERCENT_VAR_SUBSTRING,
        BatchLexer.PERCENT_VAR_REPLACE,
        BatchLexer.PERCENT_ARG,
        BatchLexer.PERCENT_TILDE,
        BatchLexer.BANG_VAR,
        BatchLexer.BANG_VAR_SUBSTRING,
        BatchLexer.BANG_VAR_REPLACE,
        BatchLexer.DQ_STRING,
        BatchLexer.MINUS,
    )

def _forSlashModOk(self, text: str) -> bool:
    # Live cmd rejects unknown FOR switches (for /b ... -> "/b was unexpected
    # at this time"). Documented extension switches are /D /R /L /F (FOR /?).
    if not text:
        return False
    return len(text) == 1 and text.lower() in "drlf"

def _forFOptionsOk(self, text: str) -> bool:
    # Structured FOR /F option-string validation aligned with live cmd syntax
    # rejects (eol= multi-char, skip= non-numeric/zero, malformed tokens=).
    # Pure predicate: do not call notifyErrorListeners (ANTLR may evaluate
    # during prediction).
    body = text[1:-1] if len(text) >= 2 and text[0] == '"' else text
    return self._forFOptionsBodyOk(body)

def _forFUnquotedOptionsOk(self, ctx) -> bool:
    # Unquoted caret-escaped options (tokens^=...^ delims^=...) must pass the
    # same structural checks as a quoted options string. Reconstruct source
    # text (including skipped spaces), strip ^ escapes, then validate.
    # Pure predicate: do not call notifyErrorListeners.
    # During adaptive prediction ctx.stop may still be unset; use LT(-1) as
    # the end of the already-matched option token span.
    import re  # isort: skip

    start_tok = ctx.start
    if start_tok is None:
        return True
    stop_tok = ctx.stop
    if stop_tok is None:
        stop_tok = self._input.LT(-1)
    if (
        stop_tok is None
        or getattr(stop_tok, "tokenIndex", -1) < start_tok.tokenIndex
    ):
        return True
    text = self._input.tokenSource.inputStream.getText(
        start_tok.start, stop_tok.stop
    )
    body = re.sub(r"\^(.)", r"\1", text, flags=re.DOTALL)
    return self._forFOptionsBodyOk(body)

def _forFOptionsBodyOk(self, body: str) -> bool:
    import re  # isort: skip

    pattern = re.compile(
        r"(?i)\b(eol|skip|delims|tokens|usebackq|useback)(=)?([^\s]*)"
    )
    for match in pattern.finditer(body):
        key = match.group(1).lower()
        has_eq = match.group(2) == "="
        raw_val = match.group(3)
        if key in ("usebackq", "useback"):
            if has_eq and raw_val:
                return False
            continue
        if not has_eq:
            return False
        if key == "eol":
            value = re.split(
                r"(?i)\b(?:skip|delims|tokens|usebackq|useback)=",
                raw_val,
                maxsplit=1,
            )[0]
            if len(value) > 1:
                return False
        elif key == "skip":
            # Live rejects non-numeric and zero (skip=0 / skip=00); skip=01 is 1.
            if not re.fullmatch(r"[0-9]+", raw_val or ""):
                return False
            if int(raw_val) == 0:
                return False
        elif key == "tokens":
            if not self._forFTokensValueOk(raw_val):
                return False
    return True

def _forFTokensValueOk(self, value: str) -> bool:
    import re  # isort: skip

    if value == "*":
        return True
    if not value:
        return False
    # tokens=1,2,4-6*  or  tokens=1-3  or  tokens=2*  or  tokens=1,*
    # (live accepts an optional comma immediately before a trailing *).
    if not re.fullmatch(
        r"[0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*(?:,?\*)?",
        value,
    ):
        return False
    # Live rejects any index whose integer value is 0 (tokens=0, tokens=00,
    # tokens=1-0, tokens=0*); tokens=01 is accepted as index 1.
    for num in re.findall(r"[0-9]+", value):
        if int(num) == 0:
            return False
    return True

def _laSetA(self) -> bool:
    # Lookahead gate so SET /P and other modes do not enter setAMode
    # (failed predicates on setAMode were reported as syntax errors).
    from BatchLexer import BatchLexer  # isort: skip

    if self._input.LA(1) != BatchLexer.SET:
        return False
    if self._input.LA(2) != BatchLexer.SLASH:
        return False
    if self._input.LA(3) != BatchLexer.WORD:
        return False
    tok = self._input.LT(3)
    return bool(tok is not None and tok.text and tok.text.lower() == "a")

def _setACaretEscapeIs(self, text: str, expected: str) -> bool:
    # CARET_ESCAPE matches '^' + one char; the second char is the escaped value.
    return len(text) == 2 and text[0] == "^" and text[1] == expected

def _setACaretShiftOk(self, first: str, second: str) -> bool:
    # Unquoted << / >> via ^<^< or ^>^>.
    return self._setACaretEscapeIs(first, "<") and self._setACaretEscapeIs(
        second, "<"
    ) or self._setACaretEscapeIs(first, ">") and self._setACaretEscapeIs(
        second, ">"
    )

def _setAQuotedOk(self, text: str) -> bool:
    # Island-parse the interior of set /A "..." with the full expression
    # grammar (shell metacharacters are ordinary operators inside quotes).
    # Pure predicate: no notifyErrorListeners (ANTLR may evaluate during
    # prediction).
    if len(text) < 2 or not (text[0] == '"' and text[-1] == '"'):
        return False
    inner = text[1:-1].replace('""', '"')
    if not inner.strip():
        return True
    try:
        from antlr4 import CommonTokenStream, InputStream  # isort: skip
        from BatchLexer import BatchLexer  # isort: skip
    except ImportError:
        # During grammar generation / offline checks, skip island parse.
        return True
    stream = InputStream(inner)
    lexer = BatchLexer(stream)
    tokens = CommonTokenStream(lexer)
    nested = type(self)(tokens)
    nested._setAQuotedIsland = True  # type: ignore[attr-defined]
    nested.removeErrorListeners()
    nested.setAExpr()
    if tokens.LA(1) != -1:
        return False
    return nested.getNumberOfSyntaxErrors() == 0

def _setAAllowShellOps(self) -> bool:
    return bool(getattr(self, "_setAQuotedIsland", False))

def _setANoUnquotedShl(self) -> bool:
    # Pure predicate (no notify): unquoted << is a live syntax error.
    from BatchLexer import BatchLexer  # isort: skip

    return not (
        self._input.LA(1) == BatchLexer.LT and self._input.LA(2) == BatchLexer.LT
    )

def _setAForVarModulo(self, text: str) -> bool:
    # In .cmd files, %% is a literal percent for SET /A modulo. The lexer may
    # emit FOR_VAR for %%3 or %%- (letter charset includes digits and '-').
    import re  # isort: skip

    return text == "%%-" or re.fullmatch(r"%%[0-9]+", text) is not None

def _gapHasSpaceOrTab(self, after_token, before_token) -> bool:
    # Lexer skips WS, so inspect the underlying char stream between tokens.
    start = after_token.stop + 1
    stop = before_token.start - 1
    if stop < start:
        return False
    gap = self._input.tokenSource.inputStream.getText(start, stop)
    return any(ch in " \t" for ch in gap)

def _requireSpaceOrTabBefore(self) -> bool:
    # Live cmd rejects glued IN(/DO(/ELSE( (reports "... was unexpected").
    # IF may still glue '(' immediately after the IF keyword (paren-wrapped
    # predicate; usually silent-false). A true then-body after a complete
    # predicate still needs space/tab before '(' (if 1==1 (echo ...)).
    # This helper is for FOR/ELSE only.
    prev = self._input.LT(-1)
    cur = self._input.LT(1)
    if self._gapHasSpaceOrTab(prev, cur):
        return True
    self.notifyErrorListeners(
        "space or tab required between keyword and '('"
    )
    return False

def _tokenOf(self, node_or_token):
    # ctx.LPAREN()/RPAREN() yield TerminalNode; compareOperand.start/stop are Tokens.
    symbol = getattr(node_or_token, "symbol", None)
    return symbol if symbol is not None else node_or_token

def _parenCompareInteriorOk(self, ctx) -> bool:
    # When both outer parens wrap a comparison, live cmd fatals if space/tab
    # sits immediately inside either paren (if ( 1==1 ) / if( 1==1) /
    # if(1==1 )). Glued forms and spaces around the compare-op remain
    # silent-false. Single-sided paren forms stay accepted (paren absorbed).
    lparen = ctx.LPAREN()
    rparen = ctx.RPAREN()
    if lparen is None or rparen is None:
        return True
    operands = ctx.compareOperand()
    if len(operands) < 2:
        return True
    left_start = operands[0].start
    right_stop = operands[1].stop
    ltok = self._tokenOf(lparen)
    rtok = self._tokenOf(rparen)
    if self._gapHasSpaceOrTab(ltok, left_start) or self._gapHasSpaceOrTab(
        right_stop, rtok
    ):
        self.notifyErrorListeners(
            "IF paren-wrapped comparison rejects interior space/tab "
            "immediately inside '(' or ')'"
        )
        return False
    return True
}

script
    : line* EOF
    ;

line
    : label
    | commandLine
    | NEWLINE
    ;

label
    : LABEL NEWLINE?
    ;

commandLine
    : statement groupStmt? ( (AMP | PIPE | AMPAMP | PIPEPIPE) statement groupStmt? )* NEWLINE?
    ;

statement
    : AT? (
        // Commit on IF/FOR so invalid predicates report syntax errors instead
        // of silently falling through to genericCmd (live cmd syntax rejects).
        {self._laIf()}? ifStmt
      | {self._laFor()}? forStmt
      // REM remarks out the rest of the physical line (live cmd), including
      // after & / && / ||; remStmt (~NEWLINE)* absorbs separators so they are
      // not chained as separate statements.
      | {self._laRem()}? remStmt
      | callStmt
      | gotoStmt
      | setStmt
      | setlocalStmt
      | endlocalStmt
      | exitStmt
      | shiftStmt
      // Newline-detached ELSE is not IF's elseClause: live cmd treats it as an
      // unknown command, and a following (block) still runs as a group.
      | detachedElseStmt
      | groupStmt
      | genericCmd
      )
    ;

// REM as command verb: remainder of the physical line is remark text (REM /?).
// A trailing multi-line '(' is left for commandLine's optional groupStmt.
remStmt
    : REM ( {self._remTokenOk()}? ~NEWLINE )*
    ;

// Detached ELSE (not same-line elseClause). Matches `else echo`, `else if ...`,
// and `else ( ... )` so orphan paren groups parse like live cmd.
detachedElseStmt
    : ELSE (groupStmt | commandTail)?
    ;

exitStmt
    : EXIT exitTail?
    ;

exitTail
    : SLASH WORD token*
    | NUMBER
    | token+
    ;

groupStmt
    : LPAREN {self._enterGroup()} block RPAREN {self._exitGroup()} commandTail?
    ;

shiftStmt
    : SHIFT token*
    ;

ifStmt
    : IF ifIOpt? ifBody
    ;

ifIOpt
    : SLASH WORD
    ;

ifBody
    : ifPredicate LPAREN {self._enterGroup()} block RPAREN {self._exitGroup()} elseClause?
    | ifPredicate {self._notOpenParenThen()}? {self._enterThenStmt()} statement {self._exitThenStmt()} elseClause?
    ;

elseClause
    : ELSE {self._requireSpaceOrTabBefore()}? LPAREN {self._enterGroup()} block RPAREN {self._exitGroup()}
    | ELSE {self._notOpenParenThen()}? statement
    ;

// Live cmd: IF ERRORLEVEL accepts a literal (optional leading minus), or a
// percent/bang/FOR expansion that yields digits after the percent pass
// (IF ERRORLEVEL %n% / !n!). Same shape for CMDEXTVERSION.
ifErrorlevelStmt
    : ERRORLEVEL MINUS? NUMBER
    | ERRORLEVEL PERCENT_VAR
    | ERRORLEVEL PERCENT_ARG
    | ERRORLEVEL PERCENT_TILDE
    | ERRORLEVEL BANG_VAR
    | ERRORLEVEL FOR_VAR
    ;

ifCmdextversionStmt
    : CMDEXTVERSION MINUS? NUMBER
    | CMDEXTVERSION PERCENT_VAR
    | CMDEXTVERSION PERCENT_ARG
    | CMDEXTVERSION PERCENT_TILDE
    | CMDEXTVERSION BANG_VAR
    | CMDEXTVERSION FOR_VAR
    ;

ifExistOperand
    : DQ_STRING
    | WORD
    | ASTERISK (DOT argWord)?
    | QUESTION+ (DOT argWord)?
    | PERCENT_VAR
    | PERCENT_TILDE
    | PERCENT_ARG
    | FOR_VAR
    | FOR_VAR_TILDE
    | BANG_VAR_SUBSTRING
    | BANG_VAR_REPLACE
    | BANG_VAR
    ;

ifDefinedOperand
    : argWord
    | PERCENT_VAR
    | FOR_VAR
    | FOR_VAR_TILDE
    | BANG_VAR
    | DQ_STRING
    ;

ifPredicate
    : NOT? ifErrorlevelStmt
    | NOT? ifCmdextversionStmt
    | NOT? DEFINED ifDefinedOperand
    | NOT? EXIST ifExistOperand
    | NOT? comparison
    // Expanded predicate forms (e.g. if %b% / if not %b% when b=a==a). Reject
    // when another operand follows without a compare-op (IF %ERRORLEVEL% 1).
    | NOT? PERCENT_VAR {self._expandedPredicateOk()}?
    | NOT? PERCENT_VAR_SUBSTRING {self._expandedPredicateOk()}?
    | NOT? PERCENT_VAR_REPLACE {self._expandedPredicateOk()}?
    | NOT? PERCENT_ARG {self._expandedPredicateOk()}?
    | NOT? PERCENT_TILDE {self._expandedPredicateOk()}?
    | NOT? BANG_VAR {self._expandedPredicateOk()}?
    | NOT? BANG_VAR_SUBSTRING {self._expandedPredicateOk()}?
    | NOT? BANG_VAR_REPLACE {self._expandedPredicateOk()}?
    | NOT? DQ_STRING {self._expandedPredicateOk()}?
    ;

// Optional outer parentheses around a comparison are accepted at parse time
// so forms like if(1==1) / if (1==1) do not hard-error. Live cmd typically
// absorbs those parens into the operand text (silent false) rather than
// treating them as C-style grouping -- see if_forms.paren_wrapped_predicate.
// Interior space/tab immediately inside both wrapping parens is a live syntax
// error (if ( 1==1 )); the predicate inspects the char stream because WS is
// skipped by the lexer -- see if_forms.paren_interior_space_fatal.
comparison
    : LPAREN? compareOperand compareOp compareOperand RPAREN?
      {self._parenCompareInteriorOk($ctx)}?
    ;

compareOp
    : EQ
    | EQU
    | NEQ
    | LSS
    | LEQ
    | GTR
    | GEQ
    ;

// One IF compare side. Allow stacked atoms so classic padding forms such as
// .%EMPTY%.==.. tokenize/parse (DOT + PERCENT_VAR + DOT). Exclude compareOp
// tokens so `a EQU b` does not swallow the operator into the left operand.
compareOperand
    : compareOperandPart+
    ;

compareOperandPart
    : DQ_STRING
    | PERCENT_TILDE
    | INVALID_PERCENT_TILDE
    | PERCENT_VAR_SUBSTRING
    | PERCENT_VAR_REPLACE
    | PERCENT_VAR
    | PERCENT_ARG
    | FOR_VAR
    | FOR_VAR_TILDE
    | BANG_VAR_SUBSTRING
    | BANG_VAR_REPLACE
    | BANG_VAR
    | WORD
    | NUMBER
    | HEX_NUMBER
    | DOT
    | MINUS
    | PLUS
    | ASTERISK
    | QUESTION
    | TILDE
    | HASH
    | DOLLAR
    | AT
    | CARET_ESCAPE
    ;

forStmt
    : FOR forSlashMod* forFOptions? forPath? FOR_VAR IN
      {self._requireSpaceOrTabBefore()}? LPAREN forList RPAREN DO forBody
    ;

forPath
    : argWord
    | DQ_STRING
    ;

forSlashMod
    : SLASH WORD {self._forSlashModOk($WORD.text)}?
    ;

forFOptions
    : DQ_STRING {self._forFOptionsOk($DQ_STRING.text)}?
    | forFUnquotedOptions
    ;

forFUnquotedOptions
    : forFOptionAnchor forFOptionExtra* {self._forFUnquotedOptionsOk($ctx)}?
    ;

forFOptionAnchor
    : argWord CARET_ESCAPE
    | CARET_ESCAPE
    ;

forFOptionExtra
    : argWord CARET_ESCAPE
    | CARET_ESCAPE
    | NUMBER
    | COMMA
    | ASTERISK
    | QUESTION
    | MINUS
    | PLUS
    | PERCENT
    | argWord
    ;

forBody
    : {self._requireSpaceOrTabBefore()}? LPAREN {self._enterGroup()} block RPAREN {self._exitGroup()}
    | {self._notOpenParenThen()}? statement
    ;

// Classic FOR set members split on space/tab (token gaps) and on comma,
// semicolon, and equals (same delimiters as batch args; see expansion
// for_forms.set_member_delimiters). Consecutive separators collapse.
// Empty sets ( ) and separator-only sets (,,) are valid and iterate zero
// times on live cmd. forListItem+ covers space/tab-separated members
// (WS is skipped by the lexer).
forList
    : forListItem (forListSep+ forListItem)* forListSep*
    | forListItem+ forListSep*
    | forListSep+
    |
    ;

forListSep
    : COMMA
    | SEMICOLON
    | EQUALS
    ;

forListItem
    : SQ_STRING
    | DQ_STRING
    | BACKTICK_STRING
    | PERCENT_VAR
    | PERCENT_TILDE
    | PERCENT_ARG
    | ASTERISK (DOT argWord)?
    // ???.txt is QUESTION+ then DOT argWord via forListItem+; a?.txt is
    // argWord then QUESTION then DOT argWord. Trailing ? may match fewer
    // characters at runtime (see expansion for_forms.wildcard_question_trailing).
    | QUESTION+ (DOT argWord)?
    | DOT argWord?
    | argWord
    | MINUS? NUMBER
    | MINUS? HEX_NUMBER
    ;

callStmt
    // Bare CALL / (CALL) / (CALL ) are valid and set ERRORLEVEL (see
    // expansion.yaml errorlevel.call_empty_*). Target is optional.
    : CALL callTarget? commandTail?
    ;

callTarget
    : COLON? EOF_KW
    | COLON? argWord
    | COLON? PERCENT_ARG
    | COLON? PERCENT_VAR
    | COLON? BANG_VAR
    | DQ_STRING
    ;

// GOTO takes the remainder of the statement as the target (spaces allowed).
// CALL keeps callTarget as the first word/token and commandTail as arguments.
// Bare GOTO with no target is a live runtime error ("No batch label specified")
// but still parses as gotoStmt (callTarget optional), matching CALL's bare form.
gotoStmt
    : GOTO callTarget? commandTail?
    ;

setStmt
    // Prefer SET /A structured expression parse (extensions-on corpus assumption).
    // Gate with lookahead so SET /P does not trip setAMode predicate errors.
    // Optional setRedirects: live cmd attaches >file / 1>nul after SET (including
    // after a quoted assignment). Trailer text before those redirects is absorbed
    // into setQuotedDiscardedTrailer, not a second statement.
    : {self._laSetA()}? SET setAMode setABody setRedirects?
    | SET setMode? setAssign? setRedirects?
    ;

setAMode
    : SLASH WORD
    ;

setABody
    : DQ_STRING {self._setAQuotedOk($DQ_STRING.text)}? setAQuotedTrailer?
    | setAExpr {self._setANoUnquotedShl()}? setARedirect*
    ;

// After set /A "expr", further non-separator / non-redirect tokens stay on the
// SET /A statement (live folds them into the arithmetic parse — often
// "Invalid number" / "Missing operator"), not a second command.
setAQuotedTrailer
    : setDiscardedToken+
    ;

// Trailing redirects after an unquoted SET /A expression (live cmd treats
 // unquoted >> / > / < as shell redirection, not arithmetic).
setARedirect
    : NUMBER? (APPEND | GT | LT | DUP_OUT | DUP_IN) token?
    ;

// SET /A expression (precedence matches expansion.yaml set_a.operator_precedence).
// Shell metachar operators (& | << >> and bare ^) are enabled only inside the
// quoted island parse (_setAQuotedIsland); unquoted forms use caret escapes.
setAExpr
    : setAAssign (COMMA setAAssign)*
    ;

setAAssign
    : setAPipe (setAAssignOp setAAssign)?
    ;

setAAssignOp
    : ASTERISK EQUALS
    | SLASH EQUALS
    | PERCENT EQUALS
    | PLUS EQUALS
    | MINUS EQUALS
    | {self._setAAllowShellOps()}? AMP EQUALS
    | {self._setAAllowShellOps()}? CARET EQUALS
    | {self._setAAllowShellOps()}? PIPE EQUALS
    | {self._setAAllowShellOps()}? LT LT EQUALS
    | {self._setAAllowShellOps()}? APPEND EQUALS
    | CARET_ESCAPE EQUALS {self._setACaretEscapeIs($CARET_ESCAPE.text, '&')}?
    | CARET_ESCAPE EQUALS {self._setACaretEscapeIs($CARET_ESCAPE.text, '^')}?
    | CARET_ESCAPE EQUALS {self._setACaretEscapeIs($CARET_ESCAPE.text, '|')}?
    | EQUALS
    ;

setAPipe
    : setAXor (setAPipeOp setAXor)*
    ;

setAPipeOp
    : {self._setAAllowShellOps()}? PIPE
    | CARET_ESCAPE {self._setACaretEscapeIs($CARET_ESCAPE.text, '|')}?
    ;

setAXor
    : setAAnd (setAXorOp setAAnd)*
    ;

setAXorOp
    // Bare ^ is accepted in unquoted SET /A source (parse structure); live cmd
    // may still caret-escape before arithmetic (see shell_metachar_quoting).
    : CARET
    | CARET_ESCAPE {self._setACaretEscapeIs($CARET_ESCAPE.text, '^')}?
    ;

setAAnd
    : setAShift (setAAndOp setAShift)*
    ;

setAAndOp
    : {self._setAAllowShellOps()}? AMP
    | CARET_ESCAPE {self._setACaretEscapeIs($CARET_ESCAPE.text, '&')}?
    ;

setAShift
    : setAAdd (setAShiftOp setAAdd)*
    ;

setAShiftOp
    : {self._setAAllowShellOps()}? LT LT
    | {self._setAAllowShellOps()}? APPEND
    | {self._setAAllowShellOps()}? GT GT
    | a=CARET_ESCAPE b=CARET_ESCAPE {self._setACaretShiftOk($a.text, $b.text)}?
    ;

setAAdd
    : setAMul (setAAddOp setAMul)*
    ;

setAAddOp
    : PLUS
    | MINUS
    ;

setAMul
    : setAUnary setAMulTail*
    ;

setAMulTail
    : setAMulOp setAUnary
    // Batch-file %% modulo is often lexed as FOR_VAR (%%3 / %%-).
    | FOR_VAR {self._setAForVarModulo($FOR_VAR.text)}? setAUnary?
    ;

setAMulOp
    : ASTERISK
    | SLASH
    | PERCENT
    | PERCENT PERCENT
    ;

setAUnary
    : setAUnaryOp setAUnary
    | setAPrimary
    ;

setAUnaryOp
    : BANG
    | TILDE
    | MINUS
    | PLUS
    | CARET_ESCAPE {self._setACaretEscapeIs($CARET_ESCAPE.text, '!')}?
    ;

setAPrimary
    : LPAREN setAExpr RPAREN
    | setALiteral
    | setAName
    ;

setALiteral
    // NUMBER WORD covers invalid forms such as 0b10 (no binary literals) that
    // still parse as a single SET /A expression on live cmd.
    : MINUS? NUMBER (DOT NUMBER)? WORD?
    | MINUS? HEX_NUMBER
    ;

setAName
    : setANamePart+
    | PERCENT_VAR
    | PERCENT_TILDE
    | PERCENT_ARG
    | PERCENT_VAR_SUBSTRING
    | PERCENT_VAR_REPLACE
    | BANG_VAR
    | BANG_VAR_SUBSTRING
    | BANG_VAR_REPLACE
    ;

setANamePart
    : argWord
    | NUMBER
    | HEX_NUMBER
    | TILDE
    | AT
    | HASH
    | DOLLAR
    | DOT
    ;

setMode
    : SLASH WORD
    ;

setAssign
    : DQ_STRING setQuotedDiscardedTrailer?
    | setTarget EQUALS setRest?
    | setTarget
    ;

// After set "name=value", non-separator / non-redirect tokens until &/&&/||/|
// or newline are discarded by live cmd and must not become a second statement
// (set "g=ok"zzz / set "g=ok" echo HI). Redirects are handled by setRedirects.
setQuotedDiscardedTrailer
    : setDiscardedToken+
    ;

setDiscardedToken
    : {self._setDiscardedTokenOk()}? token
    ;

setRedirects
    : setRedirect+
    ;

setRedirect
    : NUMBER? (APPEND | GT | LT | DUP_OUT | DUP_IN) token?
    ;

setlocalStmt
    : SETLOCAL setlocalRest?
    ;

setlocalRest
    : token+
    ;

endlocalStmt
    : ENDLOCAL commandTail?
    ;

// Unquoted SET names may include punctuation that the lexer emits as
// separate tokens (~ @ # $ ; , ( ) * + ? . - and digits). Keep consuming
// name parts until EQUALS / chain / newline so `set a~b=1` and `set var@x=3`
// remain a single setStmt (live cmd; see expansion environment_variable_names).
setTarget
    : setNamePart+
    | PERCENT_VAR
    ;

setNamePart
    : argWord
    | NUMBER
    | HEX_NUMBER
    | TILDE
    | AT
    | HASH
    | DOLLAR
    | SEMICOLON
    | COMMA
    | DOT
    | PLUS
    | MINUS
    | ASTERISK
    | QUESTION
    | LPAREN
    | {self._rparenAsTokenOk()}? RPAREN
    ;

setRest
    : token+
    ;

genericCmd
    : {self._notForToken() and self._rparenAsTokenOk() and self._genericCmdStartOk() and not self._redirectOnlyStatement()}? commandTail
    ;

commandTail
    : token+
    ;

argWord
    : WORD
    | FOR
    | IF
    | SET
    | DO
    | IN
    | EXIST
    | DEFINED
    | NOT
    | ERRORLEVEL
    | CMDEXTVERSION
    | EXIT
    | SHIFT
    | CALL
    | GOTO
    | ENDLOCAL
    | SETLOCAL
    | REM
    | {self._elseAsArgAllowed()}? ELSE
    | EQU
    | NEQ
    | LSS
    | LEQ
    | GTR
    | GEQ
    ;

token
    : DQ_STRING
    | SQ_STRING
    | BACKTICK_STRING
    | PERCENT_TILDE
    | INVALID_PERCENT_TILDE
    | PERCENT_VAR_SUBSTRING
    | PERCENT_VAR_REPLACE
    | PERCENT_VAR
    | PERCENT_ARG
    | FOR_VAR
    | FOR_VAR_TILDE
    | BANG_VAR_SUBSTRING
    | BANG_VAR_REPLACE
    | BANG_VAR
    | BANG
    | TILDE
    | AT
    | HASH
    | DOLLAR
    | CARET_ESCAPE
    | CARET
    | ASTERISK
    | QUESTION
    | {self._inlineLparenOk()}? LPAREN
    | {self._rparenAsTokenOk()}? RPAREN
    | APPEND
    | DUP_OUT
    | DUP_IN
    | GT
    | LT
    | DOT
    | BACKSLASH
    | PLUS
    | MINUS
    | COMMA
    | SEMICOLON
    | EQUALS
    | EQ
    | SLASH
    | COLON
    | PERCENT
    | argWord
    | NUMBER
    | HEX_NUMBER
    | UNMATCHED_DQ
    | UNMATCHED_SQ
    | UNMATCHED_BACKTICK
    ;

block
    : line*
    ;
