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
}

fragment DIGIT : [0-9] ;
// Live cmd accepts letters, digits, and many punctuation chars as FOR vars.
// Include ~ so bare %%~ is a FOR metavar (live cmd). %%~fI still prefers
// FOR_VAR_TILDE via longest match when a letter follows. Operators that fail
// live as FOR letters: % | & = ; < >
fragment FOR_VAR_LETTER : [a-zA-Z0-9?#$@_`[\]{}+.\-\\!*():/~] ;

LINE_COMMENT   : {self._atLineStart()}? '::' ~[\r\n]* -> skip ;

// Live cmd: a label is a line beginning with ':' and the rest of the physical
// line is the label text (spaces and most punctuation allowed). LINE_COMMENT
// ('::...') is declared first and wins for double-colon remarks.
LABEL          : {self._atLineStart()}? ':' ~[\r\n]+ ;

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

// REM is a statement verb (not line-start-only). remStmt consumes through EOL.
// Longer WORD forms such as REMCASE / remark win via longest match.
REM            : [rR][eE][mM] {self._keywordTrailerOk()}? ;
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
    : '\'' (~[\r\n'] | '\'\'')* '\''
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
NEWLINE        : [\r\n]+ ;

UNMATCHED_DQ
    : '"' (~[\r\n"] | '""')*
    ;

UNMATCHED_SQ
    : '\'' (~[\r\n'] | '\'\'')*
    ;

UNMATCHED_BACKTICK
    : '`' (~[\r\n`] | '``')*
    ;
