# Contributing

Keep experiments inspectable: preserve raw samples, verify every reconstruction and record any measurement-policy changes. Add tests for failures and boundaries. Do not submit private datasets, proprietary implementations, tokens, environment files or personal paths.

The command-line codec list is deliberately fixed. Proposals for additional public codecs should explain dependency/version recording, determinism, validation failures and how to keep installation independent. Do not add arbitrary execution plugins.

Before opening a change, install the package, run `python -m unittest discover -s tests -v`, and exercise a small generate/bench/report cycle. Use a new output directory. Changing measurement code requires regenerating the example or clearly documenting why the old example remains historical. Never edit measured numbers by hand.
