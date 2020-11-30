import os
import re
from functools import lru_cache
from typing import Dict
from typing import Iterable
from typing import List
from typing import Pattern
from typing import Tuple

from ..util.code_snippet import CodeSnippet


def is_line_allowlisted(filename: str, line: str, context: CodeSnippet) -> bool:
    for payload, regexes in zip(
        [line, context.previous_line],
        _get_allowlist_regexes_for_file(filename),
    ):
        for regex in regexes:
            if regex.search(payload):
                return True

    return False


@lru_cache(maxsize=1)
def _get_file_to_index_dict() -> Dict[str, int]:
    # Add to this mapping (and ALLOWLIST_REGEXES if applicable) lazily,
    # as more language specific file parsers are implemented.
    # Discussion: https://github.com/Yelp/detect-secrets/pull/105
    return {
        'yaml': 0,
    }


@lru_cache(maxsize=1)
def _get_comment_tuples() -> Iterable[Tuple[str, str]]:
    return (
        ('#', ''),                    # e.g. python or yaml
        ('//', ''),                   # e.g. golang
        (r'/\*', r' *\*/'),           # e.g. c
        ('\'', ''),                   # e.g. visual basic .net
        ('--', ''),                   # e.g. sql
        (r'<!--[# \t]*?', ' *?-->'),  # e.g. xml
        # many other inline comment syntaxes are not included,
        # because we want to be performant for
        # any(regex.search(line) for regex in ALLOWLIST_REGEXES)
        # calls. of course, this won't be a concern if detect-secrets
        # switches over to implementing file plugins for each supported
        # filetype.
    )


def _get_allowlist_regexes_for_file(filename: str) -> Iterable[List[Pattern]]:
    comment_tuples = _get_comment_tuples()

    _, ext = os.path.splitext(filename)
    if ext[1:] in _get_file_to_index_dict():
        comment_tuples = (comment_tuples[_get_file_to_index_dict()[ext[1:]]],)

    yield [
        _get_allowlist_regexes(comment_tuple=t, nextline=False)
        for t in comment_tuples
    ]
    yield [
        _get_allowlist_regexes(comment_tuple=t, nextline=True)
        for t in comment_tuples
    ]


# Note: Cache size should be 2x the number of comment types
@lru_cache(maxsize=12)
def _get_allowlist_regexes(comment_tuple: Tuple[str, str], nextline: bool) -> Pattern:
    start = comment_tuple[0]
    end = comment_tuple[1]
    return re.compile(
        r'{}[ \t]*{} *pragma: ?{}{}[ -]secret.*?{}[ \t]*$'.format(
            # Note: No text can precede a nextline pragma, this prevents obscuring what is allowed
            # For instance, we want to prevent the following case from working:
            #     foo = 'bar' # pragma: allowlist nextline secret
            #     pass = 'hunter2'
            r'^' if nextline else '',
            start,
            # Note: Always use allowlist, whitelist will be deprecated in the future
            r'allowlist' if nextline else r'(allow|white)list',
            r'[ -]nextline' if nextline else '',
            end,
        ),
    )
