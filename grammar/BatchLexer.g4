lexer grammar BatchLexer;

@lexer::members {
def _atLineStart(self) -> bool:
    col = self.column
    if col == 0:
        return True
    start = self._input.index - col
    prefix = self._input.getText(start, self._input.index - 1)
    return prefix.strip() == ""

def _keywordTrailerOk(self) -> bool:
    # After matching the keyword text, reject glue to percent/bang/quotes
    # and ')'. Live cmd: IF%1, SET%x%, FOR%%i, rem), if) become non-keywords
    # (WORD + trailing punctuation). Bare rem( remains REM (trailer '(' ok).
    # Note: rem. / rem/ / rem: and peers often tokenize as WORD via longest
    # match (like echo.) but still invoke the REM builtin at runtime.
    la = self._input.LA(1)
    return la not in (
        ord('%'),
        ord('!'),
        ord('"'),
        ord("'"),
        ord('`'),
        ord(')'),
    )

def _invalidPercentTildeAccept(self) -> bool:
    # Longest-match may prefer this rule over a shorter valid PERCENT_TILDE
    # (e.g. %~10 should be %~1 plus literal 0; %~2+%~3 must not glue on '+').
    # Reject INVALID when any prefix is a complete valid percent-tilde.
    import re  # isort: skip

    text = self.text
    valid = re.compile(
        r"^%~(?:[nxfpdstazNXFPDSTAZ]*\$[A-Za-z_][A-Za-z0-9_]*:[0-9]"
        r"|[nxfpdstazNXFPDSTAZ]*[0-9])$"
    )
    for end in range(3, len(text) + 1):
        if valid.match(text[:end]):
            return False
    return True

def _wordOk(self) -> bool:
    # Longest-match would otherwise glue goto:eof / call:label into one WORD.
    # Reject those so GOTO/CALL keywords win, then COLON + target (live cmd).
    import re  # isort: skip

    return re.match(r"(?i)(?:goto|call):", self.text) is None

def _remKeyword(self) -> bool:
    # REM is the keyword only when the next character does not continue a WORD
    # (remote, rem., rem/) and is not a rejected trailer (rem), rem%).
    if not self._keywordTrailerOk():
        return False
    la = self._input.LA(1)
    if la < 0 or la in (10, 13):
        return True
    if la > 127:
        return False
    return chr(la) not in (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        "0123456789_./\\:+-[]"
    )

def _remIsVerb(self) -> bool:
    # True when this REM is the command, so the rest of the physical line is a
    # remark and a trailing caret must not continue. echo rem stays data.
    # Use the token start so a later tail character does not shift the prefix.
    return self._commandPositionAtEnd(self._prefixBeforeTokenStart())

def _prefixBeforeTokenStart(self) -> str:
    start = self._tokenStartCharIndex
    if start <= 0:
        return ""
    prior = self._input.getText(0, start - 1)
    return prior.split("\n")[-1]

def _remInlineParen(self) -> bool:
    # A '(' with only whitespace before the line ending starts a group that
    # still runs. Any other '(' stays inside the remark (rem (echo hi)).
    if self._input.LA(1) != ord("("):
        return False
    look = 2
    while True:
        la = self._input.LA(look)
        if la in (ord(" "), ord("\t")):
            look += 1
            continue
        return la not in (ord("\r"), ord("\n"), -1)

def _bareCrAhead(self) -> bool:
    return self._input.LA(1) == 13 and self._input.LA(2) != 10

def _endsWithOddCaret(self) -> bool:
    count = 0
    look = -1
    while self._input.LA(look) == ord("^"):
        count += 1
        look -= 1
    return count % 2 == 1

def _skipSpaces(self, text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\r":
        index += 1
    return index

def _readWord(self, text: str, index: int) -> tuple[str, int]:
    start = index
    while index < len(text) and text[index] not in " \t\r&|()<>\"":
        index += 1
    return text[start:index], index

def _skipQuote(self, text: str, index: int) -> int:
    index += 1
    while index < len(text) and text[index] != '"':
        index += 1
    if index < len(text):
        index += 1
    return index

def _skipParen(self, text: str, index: int) -> int:
    depth = 0
    while index < len(text):
        char = text[index]
        index += 1
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return index

def _skipRedirect(self, text: str, index: int) -> int:
    # Return index unchanged when text[index] is not a redirect.
    cursor = index
    while cursor < len(text) and text[cursor].isdigit():
        cursor += 1
    if cursor >= len(text):
        return index
    if text.startswith(">>", cursor) or text.startswith(">&", cursor):
        cursor += 2
    elif text.startswith("<&", cursor):
        cursor += 2
    elif text[cursor] in "<>":
        cursor += 1
    else:
        return index
    cursor = self._skipSpaces(text, cursor)
    if cursor < len(text) and text[cursor] == '"':
        return self._skipQuote(text, cursor)
    if cursor < len(text) and text[cursor] not in "&|()<>":
        _word, cursor = self._readWord(text, cursor)
    return cursor

def _skipOperand(self, text: str, index: int) -> int:
    if index >= len(text):
        return index
    if text[index] == '"':
        return self._skipQuote(text, index)
    if text[index] == "(":
        return self._skipParen(text, index)
    _word, index = self._readWord(text, index)
    return index

def _afterForDo(self, text: str, index: int) -> int:
    while index < len(text):
        index = self._skipSpaces(text, index)
        if index >= len(text):
            return index
        if text[index] == "(":
            index = self._skipParen(text, index)
            continue
        word, index = self._readWord(text, index)
        if word.lower() == "do":
            return index
    return index

def _afterIfCondition(self, text: str, index: int) -> tuple[int, bool]:
    # Return where the IF body starts, and whether that position is a command.
    while True:
        index = self._skipSpaces(text, index)
        if index >= len(text):
            return index, True
        if text[index] == "(":
            return self._skipParen(text, index), True
        word, nxt = self._readWord(text, index)
        if word.lower() in ("not", "/i"):
            index = nxt
            continue
        break
    if index >= len(text):
        return index, True
    if text[index] == "(":
        return self._skipParen(text, index), True
    word, nxt = self._readWord(text, index)
    low = word.lower()
    if low in ("exist", "defined", "errorlevel", "cmdextversion"):
        index = self._skipSpaces(text, nxt)
        if index >= len(text):
            return index, False
        return self._skipOperand(text, index), True
    if "==" in word:
        return nxt, True
    index = self._skipSpaces(text, nxt)
    if index >= len(text):
        return index, False
    op, nxt = self._readWord(text, index)
    op_low = op.lower()
    if op == "==" or op_low in ("equ", "neq", "lss", "leq", "gtr", "geq"):
        index = self._skipSpaces(text, nxt)
        if index >= len(text):
            return index, False
        return self._skipOperand(text, index), True
    if op.startswith("=="):
        return nxt, True
    return nxt, True

def _commandPositionAtEnd(self, text: str) -> bool:
    index = 0
    command = True
    while index < len(text):
        index = self._skipSpaces(text, index)
        if index >= len(text):
            break
        redirected = self._skipRedirect(text, index)
        if redirected != index:
            index = redirected
            continue
        char = text[index]
        if char == "@" and command:
            index += 1
            continue
        if char in "&|":
            command = True
            index += 1
            continue
        if char == "(":
            command = True
            index += 1
            continue
        if char == ")":
            command = False
            index += 1
            continue
        if char == '"':
            index = self._skipQuote(text, index)
            command = False
            continue
        word, index = self._readWord(text, index)
        if word == "":
            index += 1
            continue
        if command and word.lower() == "for":
            index = self._afterForDo(text, index)
            command = True
            continue
        if command and word.lower() == "if":
            index, command = self._afterIfCondition(text, index)
            continue
        command = False
    return command
}

fragment DIGIT : [0-9] ;
// Live cmd accepts letters, digits, and many punctuation chars as FOR vars.
// Include ~ so bare %%~ is a FOR metavar (live cmd). %%~fI still prefers
// FOR_VAR_TILDE via longest match when a letter follows. Operators that fail
// live as FOR letters: % | & = ; < >
fragment FOR_VAR_LETTER : [a-zA-Z0-9?#$@_`[\]{}+.\-\\!*():/~] ;

// A bare CR is not a line ending (cmd.exe drops it), so a remark runs to LF.
// An odd trailing caret continues, and the joined physical lines stay inside
// the remark. An even run (^^) does not. LINE_COMMENT is declared before LABEL.
LINE_COMMENT
    : {self._atLineStart()}? '::'
      ( ~[\r\n] | {self._bareCrAhead()}? '\r' )*
      ( {self._endsWithOddCaret()}? '\r'? '\n'
        ( ~[\r\n] | {self._bareCrAhead()}? '\r' )*
      )*
      -> skip
    ;

// Live cmd: a label is a line beginning with ':' and the rest of the physical
// line is the label text (spaces and most punctuation allowed). A bare CR
// does not end the label. An odd trailing caret continues, and those following
// physical lines are part of this label rather than later commands.
LABEL
    : {self._atLineStart()}? ':'
      ( ~[\r\n] | {self._bareCrAhead()}? '\r' )+
      ( {self._endsWithOddCaret()}? '\r'? '\n'
        ( ~[\r\n] | {self._bareCrAhead()}? '\r' )*
      )*
    ;

AT             : '@' ;
// Bare # / $ appear in args and SET names (live cmd). Keep as distinct
// tokens so they are not dropped as recognition errors outside %name%.
HASH           : '#' ;
DOLLAR         : '$' ;
// Bare { } [ ] are ordinary cmd characters (echo payloads, SET names such as
// a{b} / arr[1]). Distinct tokens, same as HASH / DOLLAR. Glued echo[ / echo]
// stay one WORD via longest match because '[' / ']' are WORD continuations.
LBRACE         : '{' ;
RBRACE         : '}' ;
LBRACK         : '[' ;
RBRACK         : ']' ;

// REM as the command verb remarks out the rest of the physical line, so a
// trailing caret does not continue. The '(' of a following parenthesized
// group is left for the parser. echo rem stays a short keyword token.
// REMCASE / rem. stay WORD because _remKeyword rejects a WORD continuation.
REM
    : [rR][eE][mM] {self._remKeyword()}?
      ( {self._remIsVerb()}?
        ( ~[\r\n(] | {self._remInlineParen()}? '(' )
      )*
    ;
FOR            : [fF][oO][rR] {self._keywordTrailerOk()}? ;
IF             : [iI][fF] {self._keywordTrailerOk()}? ;
CALL           : [cC][aA][lL][lL] {self._keywordTrailerOk()}? ;
GOTO           : [gG][oO][tT][oO] {self._keywordTrailerOk()}? ;
SET            : [sS][eE][tT] {self._keywordTrailerOk()}? ;
SETLOCAL       : [sS][eE][tT][lL][oO][cC][aA][lL] {self._keywordTrailerOk()}? ;
ENDLOCAL       : [eE][nN][dD][lL][oO][cC][aA][lL] {self._keywordTrailerOk()}? ;
DO             : [dD][oO] {self._keywordTrailerOk()}? ;
IN             : [iI][nN] {self._keywordTrailerOk()}? ;
EXIST          : [eE][xX][iI][sS][tT] {self._keywordTrailerOk()}? ;
DEFINED        : [dD][eE][fF][iI][nN][eE][dD] {self._keywordTrailerOk()}? ;
NOT            : [nN][oO][tT] {self._keywordTrailerOk()}? ;
ERRORLEVEL     : [eE][rR][rR][oO][rR][lL][eE][vV][eE][lL] {self._keywordTrailerOk()}? ;
CMDEXTVERSION  : [cC][mM][dD][eE][xX][tT][vV][eE][rR][sS][iI][oO][nN] {self._keywordTrailerOk()}? ;
ELSE           : [eE][lL][sS][eE] {self._keywordTrailerOk()}? ;
EXIT           : [eE][xX][iI][tT] {self._keywordTrailerOk()}? ;
SHIFT          : [sS][hH][iI][fF][tT] {self._keywordTrailerOk()}? ;
EOF_KW         : [eE][oO][fF] {self._keywordTrailerOk()}? ;

LPAREN         : '(' ;
RPAREN         : ')' ;
AMP            : '&' ;
PIPE           : '|' ;
AMPAMP         : '&&' ;
PIPEPIPE       : '||' ;
APPEND         : '>>' ;
DUP_OUT        : '>&' ;
DUP_IN         : '<&' ;
GT             : '>' ;
LT             : '<' ;
EQ             : '==' ;
COLON          : ':' ;
SLASH          : '/' ;
EQUALS         : '=' ;
COMMA          : ',' ;
SEMICOLON      : ';' ;
DOT            : '.' ;
BACKSLASH      : '\\' ;
PLUS           : '+' ;
MINUS          : '-' ;

EQU            : [eE][qQ][uU] ;
NEQ            : [nN][eE][qQ] ;
LSS            : [lL][sS][sS] ;
LEQ            : [lL][eE][qQ] ;
GTR            : [gG][tT][rR] ;
GEQ            : [gG][eE][qQ] ;
CARET          : '^' ;
ASTERISK       : '*' ;
// Single-character wildcard in file-set masks (FOR /?, DIR, IF EXIST, etc.).
// Distinct from FOR_VAR_LETTER '?' which only applies inside %%? forms.
QUESTION       : '?' ;

// '^' plus CRLF is one escaped ending. The CR is optional so LF-only
// fixtures continue too. A CR that is not followed by LF is BARE_CR, not
// this rule.
LINE_CONTINUATION
    : '^' '\r'? '\n' -> skip
    ;

CARET_ESCAPE
    // Shell metacharacters and whitespace (e.g. FOR /F tokens^=1^ delims^=).
    // Digits/letters after ^ stay as CARET + WORD/NUMBER so SET /A XOR
    // (e.g. "x=5^1") tokenizes correctly; ^^ remains CARET_ESCAPE.
    : '^' ([&|<>()^!"%@,;=] | [ \t])
    ;

DQ_STRING
    : '"' (~'"' | '""')* '"'
    ;

// Apostrophes are not cmd string delimiters and do not pair across lines.
// A same-line pair is SQ_STRING; an odd quote is UNMATCHED_SQ through EOL.
// Cross-line pairing would swallow later parentheses inside command groups.
SQ_STRING
    : '\'' (~[\n'] | '\'\'')* '\''
    ;

BACKTICK_STRING
    : '`' (~'`' | '``')* '`'
    ;

// Valid CALL/? percent-tilde for batch parameters (%~1, %~dp0, %~$PATH:1).
// Letter metavars use FOR_VAR_TILDE (%%~). Modifiers are nxfpdstaz only.
PERCENT_TILDE
    : '%' '~' (
        [nxfpdstazNXFPDSTAZ]* '$' [a-zA-Z_][a-zA-Z0-9_]* ':' [0-9]
      | [nxfpdstazNXFPDSTAZ]* [0-9]
      )
    ;

// Live cmd rejects other %~ forms as invalid path-operator substitution
// (including %~*, bad letters, and %~name% that look like env vars).
// Same-length ties prefer PERCENT_TILDE (declared above).
INVALID_PERCENT_TILDE
    : '%' '~' (
        '*'
      | (~[%\r\n \t&|<>()^,;=+*/])+ '%'?
      )
      {self._invalidPercentTildeAccept()}?
      {
        self.getErrorListenerDispatch().syntaxError(
            self,
            None,
            self._tokenStartLine,
            self._tokenStartColumn,
            'invalid percent-tilde substitution: ' + self.text,
            None,
        )
      }
    ;

// Live cmd accepts a wide env-name charset inside %name% (spaces and most
// punctuation). Exclude '%' (terminator), '=' (SET forbids in names), and
// newlines. Substring/replace forms also exclude ':' in the name portion.
// Names must not start with '~': %~... is percent-tilde (rules above).
fragment ENV_NAME_CHAR : ~[%=\r\n] ;
fragment ENV_NAME_CHAR_NO_COLON : ~[%:=\r\n] ;
// Digits and '*' cannot start %name%: %0-%9 / %* are always PERCENT_ARG
// (longest-match would otherwise treat "%*) do echo %" as one PERCENT_VAR
// when a later %% closes the name). Digit-leading names use !name! instead.
fragment ENV_NAME_START : ~[%=\r\n~0-9*] ;
fragment ENV_NAME_START_NO_COLON : ~[%:=\r\n~0-9*] ;

PERCENT_VAR_SUBSTRING
    : '%' ENV_NAME_START_NO_COLON ENV_NAME_CHAR_NO_COLON* ':' '~' '-'? DIGIT+ (',' '-'? DIGIT*)? '%'
    ;

PERCENT_VAR_REPLACE
    : '%' ENV_NAME_START_NO_COLON ENV_NAME_CHAR_NO_COLON* ':' (~'%' | '%%')+ '=' (~'%' | '%%')* '%'
    ;

PERCENT_VAR
    : '%' ENV_NAME_START ENV_NAME_CHAR* '%'
    ;

PERCENT_ARG
    : '%' [0-9*]
    ;

FOR_VAR_TILDE
    : '%%' '~' ([a-zA-Z]* '$' [a-zA-Z_][a-zA-Z0-9_]* ':' FOR_VAR_LETTER | [a-zA-Z]* FOR_VAR_LETTER)
    ;

FOR_VAR
    : '%%' FOR_VAR_LETTER
    ;

fragment DELAYED_NAME_CHAR : ~[!\r\n] ;
fragment DELAYED_NAME_CHAR_NO_COLON : ~[!:\r\n] ;

BANG_VAR_SUBSTRING
    : '!' DELAYED_NAME_CHAR_NO_COLON+ ':' '~' '-'? DIGIT+ (',' '-'? DIGIT*)? '!'
    ;

BANG_VAR_REPLACE
    : '!' DELAYED_NAME_CHAR_NO_COLON+ ':' (~[!\r\n] | '!!')+ '=' (~[!\r\n] | '!!')* '!'
    ;

BANG_VAR
    : '!' DELAYED_NAME_CHAR+ '!'
    ;

BANG
    : '!'
    ;

TILDE
    : '~'
    ;

PERCENT
    : '%'
    ;

// Include [] (\u005B/\u005D) so blank-line forms like echo[ / echo] stay a
// single WORD token (live cmd accepts those ECHO blank-line spellings).
// Colon stays in WORD for drive paths (C:\...) and /X:value switches. A
// predicate rejects goto:/call: glue so those tokenize as KEYWORD COLON target.
// Non-ASCII (for example typographic quotes U+201C/U+201D) is ordinary text in
// live cmd and must not raise token recognition errors.
WORD           : (
                   [a-zA-Z_]
                 | ~[\u0000-\u007F]
                 )
                 (
                   [a-zA-Z0-9_./\\:+\-\u005B\u005D]
                 | ~[\u0000-\u007F]
                 )*
                 {self._wordOk()}?
               ;
HEX_NUMBER     : '0' [xX] [0-9a-fA-F]+ ;
NUMBER         : DIGIT+ ;

WS             : [ \t]+ -> skip ;
// cmd.exe reads a physical line up to LF. The CR of a CRLF pair stays, so
// '^' CRLF is still one escaped ending. One or more LF endings, each with
// an optional CR, are one NEWLINE. A CR with no LF is not a NEWLINE.
NEWLINE        : ('\r'? '\n')+ ;
BARE_CR        : '\r' -> skip ;

UNMATCHED_DQ
    : '"' (~[\n"] | '""')*
    ;

UNMATCHED_SQ
    : '\'' (~[\n'] | '\'\'')*
    ;

UNMATCHED_BACKTICK
    : '`' (~[\n`] | '``')*
    ;
