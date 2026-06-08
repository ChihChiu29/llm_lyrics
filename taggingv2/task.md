Goal: create a new lyrics tagging cli

Base the design on suno_tag_cli.py, but change its workflow to the following:

1. At the beginning, ask users to choose *multiple* models (maybe use empty input as "stop")

2. Once given the song title and lyrics, *for each of the chosen model from step 1*, generates 5 styles best suited for the lyrics (using "prompts/style_system.md"), print them out, then add (style, model) to a list.

3. We now have a long list of (style, model) from step 2. For each (style, model) from step 2:

  - For each model from step 1, use it to score the style between 1-10 (10 is the best fit), add the into to the list so each item become (style, model_who_made_the_style, {scoring_model: score, ...})

  - When scoring, make sure to pass the lyrics to the scoring model so it has context.

  - Scoring can be done in batch, maybe every 5 styles, otherwise it can be too slow.

4. We now have a long list of (style, mode_who_made_the_style, {scoring_model: score, ...}), then:

  - For each style, compute the average score from all scoring models.

  - Rank all styles by average scoring models, higher ones are at the top.

5. Write result into output/title_yyyy_mm_dd.md:

  - Start with song title and lyrics

  - Then write all styles sorted by step 4, their average score, which model made the style, then a bullet pointed list of scores and scoring models.

Ask me if some steps are vague or unclear.