terminga-proxy
==============

terminga is a TUI for Icinga. It interacts with the Icinga API. Sadly,
Icinga's API module currently has a memory leak. If you use terminga
long enough, your Icinga process will be killed by Linux's OOM killer.

This project is a workaround for that memory leak. We query Icinga's
PSQL database directly and return JSON data similar to the normal API.

Note: *We only return exactly those fields that are used by terminga.
This is not a generic API wrapper.*
