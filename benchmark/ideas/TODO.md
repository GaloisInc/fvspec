# TODOs

## actually implement central fn (not just sig) at benchmark-generation-time.

We also want to autoformalize the central fn being tested. To MVP this, just prompt the language model to give the implementation in the same loop/prompt that it gives the signature for it and the theorem. We are still `sorry`ing out the theorem! 

Should be in a `generate.scaffold.infer_funcs` submodule

## Problem: full source of function not in training data! 

is it one of the `deps`? 

## run `plausible` once main function is autoformalized and spec compiles with sry

`thefile.replace("sorry", "plausible")`

## fix unit test extraction

## append unit tests when you run plausible.
