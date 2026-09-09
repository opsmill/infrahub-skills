# Comparisons Cite Official Docs or Say Unsure

"What is NetBox's X in Infrahub?" is answered as a translation whose
competitor half is officially sourced or explicitly unverified.

## Why it matters

Learners arriving from NetBox or Nautobot frame everything through the
tool they know, and a wrong claim about that tool destroys trust in the
whole lesson. Competitor behavior asserted from memory is the fastest
way to teach something false about a product this repo cannot test.

## The rule

Name the competitor concept, then teach the Infrahub equivalent
normally (its claims cite docs.infrahub.app as always). When no direct
equivalent exists, say so and teach the nearest one. The competitor-side
claim carries a line in Explain starting exactly `**Comparison source:**`
whose value is either a URL on that tool's official documentation
(NetBox: docs.netbox.dev or netboxlabs.com/docs; Nautobot:
docs.nautobot.com) that you fetched and confirmed supports the claim, or
the word `unverified`, in which case the prose says you are unsure of
the competitor side and are going by the learner's description. Blogs,
forums, and recollection never ground a taught comparison.

## Correct

    In NetBox, config contexts attach JSON data to devices by scope.
    **Comparison source:** https://docs.netbox.dev/en/stable/features/context-data/
    In Infrahub the same need is met by transforms over your own data.
    See https://docs.infrahub.app/topics/transformation for the model.

## Incorrect

    NetBox handles this with config contexts, which work the same way
    as transforms.

Asserted from memory: no source line, no uncertainty, and "the same
way" is exactly the kind of claim that turns out false.
