Fix the key generation in `src/cache.py`. Combine the arguments with a separator or a tuple so that ('ab', 'c') and ('a', 'bc') no longer produce the same key.
