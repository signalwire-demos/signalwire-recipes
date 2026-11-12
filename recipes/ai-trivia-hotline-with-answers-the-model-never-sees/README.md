# AI trivia hotline: a game graded in code with an answer key the model never sees

> A trivia hotline demo built to show a voice AI agent that keeps no game state and never sees the answers. The handler grades each answer, writes the score and the next question, and ends the game itself.

**Scenario:** A caller plays five trivia questions and hears a running score, graded on the server with fuzzy matching

## What this demonstrates

The model keeps no game state and never sees the answer key. It sees the
current question through `${global_data.question}` and nothing else. The
`submit_answer` handler reads the question id from `global_data`, grades the
caller's words in Python with fuzzy matching, and writes the new round, score
and next question back. After `ROUNDS` questions it calls
`swml_change_step("final_score")`. Every call to `submit_answer` moves the game
on a round, so the model cannot retry or probe for an answer. The tests check
that no accepted answer appears anywhere in the dumped SWML or in any
`global_data` the handler writes.

The host greets the caller and asks a question. Whatever the caller says is
graded on the server, and the host says whether it was right, gives the running
score, and asks the next question. After five rounds the host reads the final
score and says goodbye. Each call gets its own random set of questions from
`data/questions.json`.

## How it works

Two steps. `play` has one tool and `valid_steps=[]`, so only the handler can
end the game, and `final_score` has `set_functions([])`, `valid_steps=[]` and
`set_end(True)`. A dynamic config callback, `start_game`, draws the question
order per call and seeds `global_data` before the model speaks. The step text
reads `${global_data.question}` and `${global_data.score}`, so the prompt never
changes while the data under it does.

Where each mechanism lives in the repository:

- `define_contexts` and `add_step`: `app.py`, `TriviaAgent.__init__`
- `set_functions(["submit_answer"])` and `set_valid_steps([])`: step `play`
- `set_functions([])`, `set_valid_steps([])` and `set_end(True)`: step `final_score`
- `update_global_data` then `swml_change_step`: the `submit_answer` handler
- `set_dynamic_config_callback`, the per-call question order: `start_game`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a question file under
`data/`. It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here
are verified against. Its claims are proven by its own tests, not by a
verifier in this repository. The repository carries no licence file at the
time of writing, which is its owner's to add.

The game state lives in `global_data` on the call, not on this server. The
agent is stateless, and `agent.run()` deploys unchanged to AWS Lambda or
Google Cloud Functions.

## What to change first

Open `config.py`: point `QUESTIONS_FILE` at your own question file, with every
accepted spelling in `answers`, set `ROUNDS`, and tune `FUZZY_TOLERANCE`
(lower accepts sloppier answers). `SHOW_NAME` and `VOICE` set the host.
