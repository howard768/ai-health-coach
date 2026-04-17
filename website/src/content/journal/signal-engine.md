---
title: "How Meld finds patterns in your data"
description: "Most AI health apps read your data and guess. Meld runs actual statistical tests. Here's how the pattern discovery engine works under the hood."
pubDate: 2026-04-15
author: "Brock Howard"
excerpt: "When Meld says your deep sleep improves on high-protein days, that's not a hunch. Here's the pipeline that produces it."
---

When Meld says "your deep sleep improved 18% on days you ate more than 110g of protein by 2pm," that is not a guess. It is not a ChatGPT hallucination. It is the output of a pipeline that tested the correlation, controlled for false discovery, and validated it against a published study.

Here is how that pipeline works.

## Step 1: collect 30 days

Meld reads from every source you connect: Oura for sleep and HRV, Apple Health for steps and heart rate, Peloton and Garmin for workouts, your food logs for nutrition. It runs in the background, pulling new data every few hours.

After about 30 days, Meld has enough paired observations to start looking for patterns that are statistically meaningful, not just interesting-looking.

## Step 2: test every pair

Your body is a system. Sleep affects recovery. Recovery affects training capacity. Training affects appetite. Appetite affects nutrition. Nutrition affects sleep.

Meld tests correlations across every domain, not just the obvious ones. Protein intake vs deep sleep minutes. Workout intensity vs next-day HRV. Dinner timing vs sleep onset latency. Steps vs next-day readiness.

Each pair gets tested with both Pearson (linear) and Spearman (rank-order) correlation. Both methods must agree in direction for the pair to advance. This catches cases where one method sees a signal the other doesn't.

## Step 3: control for false discovery

This is where most AI health apps stop. They find a correlation and show it to you. But here is the problem: if you test 50 metric pairs, 2-3 of them will look correlated purely by chance. That is how statistics works.

Meld applies Benjamini-Hochberg false discovery rate correction. It takes every pair that looks significant, ranks them by p-value, and adjusts the threshold so the overall false-discovery rate stays below 10%. This means: out of every 10 patterns Meld shows you, at most 1 is likely noise.

Without this step, you would get exciting-sounding patterns that don't hold up. With it, you get patterns you can act on.

## Step 4: validate against research

If a pattern survives the statistical tests, Meld checks it against a curated library of published research. When there is a matching study, the pattern gets upgraded to "literature-supported" confidence, and the coach can cite the specific paper when it tells you about it.

For example: protein intake correlating with deep sleep quality is supported by Peuhkuri K, et al. "Diet promotes sleep duration and quality." (*Nutrition Research*, 2012). Meld links this study directly in the coaching message.

When there is no matching paper, Meld still shows the pattern but labels it as "developing" or "established" based on the statistical strength alone. You always know how confident the finding is.

## Step 5: rank and surface

On any given day, Meld might have 5-10 active patterns for you. It ranks them by a weighted score: how strong the effect is, how confident the finding is, how actionable it is (can you do something about it today?), how novel it is (have you already seen this one?), and whether published research supports it.

The one that scores highest becomes the insight your coach tells you about. Not a random chart. Not all five at once. One specific, actionable finding, ranked by what matters most right now.

## What this means for you

You do not have to understand any of this. Meld handles the statistics in the background. What you see is a coach that says clear, specific things like "your deep sleep improved on high-protein days" and lets you tap to see the evidence.

But if you do care about rigor: 413 automated tests verify this pipeline on every release. The coach does not tell you things the numbers do not support.

Most AI health apps are a chatbot on top of a dashboard. Meld is a statistical discovery engine on top of your real data, with a coach that explains the findings in plain English.

That is the difference.

---

Waitlist open at [heymeld.com](https://heymeld.com). iOS first. We will email you the week we ship.

-- Brock
Founder, Meld
