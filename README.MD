
## Quick start (`overhaul` branch)


1) Have the CPMpy source code somewhere available
```bash
git clone https://github.com/CPMpy/cpmpy.git
```

2) Install the fuzz tester
```bash
git clone https://github.com/CPMpy/fuzz-test.git
cd fuzz-test
git checkout overhaul
pip install -r requirements.txt
pip install -e /path/to/cpmpy[all,io.all]
```

3) (Re)-generate the models (must be redone upon every API change)
```bash
python model_generator.py -c /path/to/cpmpy -o models  # (re)generate the seed models
```

4) Run the fuzz tester
```
python fuzz_test.py --max-failed-tests 1
```

Found bugs are written to `output/` (pickle + text report per failure).

## Usages guide
### Installation
```bash
git clone https://github.com/CPMpy/fuzz-test.git # Clone the git repo
pip install -r requirements.txt # install the necessary packages 
```
### Usage
#### fuzz_test
Run mutation-based fuzz tests for CPMpy solvers:

```bash
python fuzz_test.py [-h] [-s SOLVER] [-m MODELS] [-o OUTPUT_DIR] [-g]
                    [--max-failed-tests MAX_FAILED_TESTS] [--max-minutes MAX_MINUTES]
                    [--max-fuzz-seconds MAX_FUZZ_SECONDS] [-mpm MUTATIONS_PER_MODEL]
                    [-p AMOUNT_OF_PROCESSES] [--seed SEED] [--agent] [--non-interactive]
                    [--quiet] [--output {text,json}] [--progress {auto,curses,dots,none}]
                    [--dry-run]
```

The fuzz test has 5 different verifiers:
- metamorphic_verifier.py : Satisifiability check
- equivalance_verifier.py : All-Solutions check
- model_counting_verifier.py: Solution count check
- optimization_verifier.py: Optimisation check
- solution_check_verifier.py: 1-Solution check

How does fuzz_test work? It picks a random verifier, a random model, and random mutations on that model, then runs the verifier and checks whether the results hold. If a check fails or another error occurs, the application writes a separate log for each failure in the output directory (configurable via `--output-dir`). The logs contain details on how and why the error occurred.

#### parameters
| Option | Description |
|--------|-------------|
| `-h, --help` | Show help message and exit. |
| `-s, --solver SOLVER` | Solver to use. |
| `-m, --models MODELS` | Directory containing model folders. |
| `-o, --output-dir OUTPUT_DIR` | Directory to store failure artifacts and `run_stats.json`. |
| `-g, --skip-global-constraints` | Skip global constraints when testing. |
| `--max-failed-tests MAX_FAILED_TESTS` | Stop after this many failed tests. Default: no limit. |
| `--max-minutes MAX_MINUTES` | Maximum run time in minutes. Default: run indefinitely. |
| `--max-fuzz-seconds MAX_FUZZ_SECONDS` | Maximum time in seconds for a single fuzz test. Default: 10. |
| `-mpm, --mutations-per-model MUTATIONS_PER_MODEL` | Number of mutations executed on every model. |
| `-p, --amount-of-processes AMOUNT_OF_PROCESSES` | Number of worker processes. |
| `--seed SEED` | Master seed for reproducibility. |
| `--agent` | Shortcut for `--non-interactive --quiet --output json --progress none`. |
| `--non-interactive` | Fail fast and avoid terminal UI behavior. |
| `--quiet` | Suppress progress and human-readable banners. |
| `--output {text,json}` | Final stdout format. |
| `--progress {auto,curses,dots,none}` | Progress display mode. |
| `--dry-run` | Validate configuration and print the planned run without starting workers. |

The models directory should have category subfolders (for example `sat`, `optimization`, `unsat`) below generated test-suite folders:

```
├── models
  ├── pickle_examples
    ├── sat
      ├── model1.pickle
      ├── model2.pickle
      ├── ...
    ├── optimization
      ├── model1.pickle
      ├── model2.pickle
      ├── ...
    ├── ...
  ├── ...
```

#### examples
```bash
python fuzz_test.py --max-minutes 10 -s ortools
python fuzz_test.py --agent --max-minutes 1 -s ortools
python fuzz_test.py --dry-run --agent --models models --output-dir output
python fuzz_test.py --output json --progress none --max-failed-tests 1
```

Agent-friendly runs always write `run_stats.json` to the output directory. Existing failure artifacts (`.pickle` and `.txt`) are still written as before.

## Rerun bugs
The `fuzz_test_rerunner.py` script reproduces and debugs errors found during fuzz testing. When `fuzz_test.py` finds errors, it saves them as pickle files in the output directory. The rerunner helps investigate these errors by:

1. Loading and replaying the exact sequence of mutations that caused the error
2. Checking if bugs persist on other CPMpy branches
3. Allowing you to debug the specific conditions that triggered the failure

```bash
python fuzz_test_rerunner.py [-h] [-m FAILED_MODEL_FILE] [-o OUTPUT_DIR] [-p AMOUNT_OF_PROCESSES]
                             [-e ELABORATE] [-r] [-M MOVE_DIR] [--max-fuzz-seconds MAX_FUZZ_SECONDS]
                             [--mutator-indices MUTATOR_INDICES]
```

#### parameters
| Option | Description |
|--------|-------------|
| `-h, --help` | Show help message and exit. |
| `-m, --failed_model_file FAILED_MODEL_FILE` | Path to a single pickle file or a directory containing multiple pickle files. |
| `-o, --output-dir OUTPUT_DIR` | Directory to store the output (will be created if it does not exist). |
| `-p, --amount-of-processes AMOUNT_OF_PROCESSES` | Number of worker processes. |
| `-e, --elaborate ELABORATE` | Elaborate print; also show filenames of errors that are re-run. |
| `-r, --remove` | Remove fixed error files. |
| `-M, --move-dir MOVE_DIR` | Directory to move fixed error files to. |
| `--max-fuzz-seconds MAX_FUZZ_SECONDS` | |
| `--mutator-indices MUTATOR_INDICES` | Comma-separated list of mutator indices to re-apply (e.g. `0,2,4`), or `none` to apply no mutators. If not provided, all mutators are re-applied. |

#### output
The rerunner prints how many tests still failed and how many no longer failed. You can optionally remove or move files that no longer fail.

## Model Generator
A Python application to generate models from the CPMpy tests. It extracts solvable test models from CPMpy's unittest suite, providing a diverse set of real-world models that can be used as input for fuzz testing.

```bash
python model_generator.py [-h] -c CPMPY_DIR [-o OUTPUT_DIR]
```

#### parameters
| Option | Description |
|--------|-------------|
| `-h, --help` | Show help message and exit. |
| `-c, --cpmpy-dir CPMPY_DIR` | The directory were cpmpy is located. |
| `-o, --output-dir OUTPUT_DIR` | The directory to store the output (will be created if it does not exist). |

The script works by:
1. Running all unittest cases from the specified CPMpy installation
2. Capturing models that are solved during test execution
3. Saving these models as pickle files in the output directory

These extracted models serve as the starting point for mutation-based fuzz testing, ensuring that the initial models are valid and solvable before mutations are applied.


## Acknowledgments

Part of the development received funding through Prof. Tias Guns his European Research Council (ERC) Consolidator grant, under the European Union’s Horizon 2020 research and innovation programme (grant agreement No 101002802, [CHAT-Opt](https://people.cs.kuleuven.be/~tias.guns/chat-opt.html)).

You can cite HURRICANE as follows: 
> W. Vanroose, I. Bleukx, J. Devriendt, D. Tsouros, H. Verhaeghe, and T. Guns.
> Mutational fuzz testing for constraint modeling systems. 
> In CP, volume 307 of LIPIcs, 29:1–29:25. Schloss Dagstuhl, 2024

```bibtex
@inproceedings{vanroose2024mutational,
  author       = {Wout Vanroose and
                  Ignace Bleukx and
                  Jo Devriendt and
                  Dimos Tsouros and
                  H{\'{e}}l{\`{e}}ne Verhaeghe and
                  Tias Guns},
  title        = {Mutational Fuzz Testing for Constraint Modeling Systems},
  booktitle    = {{CP}},
  series       = {LIPIcs},
  volume       = {307},
  pages        = {29:1--29:25},
  publisher    = {Schloss Dagstuhl},
  year         = {2024}
}
```

# Experimental setup in the paper
This information only aplies to the version of this repository that was used in the paper.
(if anyone was trying to reproduce the results)
Repository for the future testing of CPMpy with the use of differential testing and metamorphic testing.

It also will contain a tool to reduce the model in case a bug is found and a way to obtain CPMpy models to test CPMpy using the two techniques above.

This repository builds futher on the work of the thesis by Ruben Kindt which was under guidance of Tias Guns and Ignace Bleukx.

If an error is found in an internal function, a file with the name internalfunctioncrash will be created, containing 
function, argument, originalmodel, error and mutators used that cause the error.

If a model becomes unsat after transformations, a file with the name lasterrormodel is created, containing 
model (the unsat model), originalmodel, mutators (list of mutators that were used)

These files can be read by using pickle.load, as you can see in the example code in errorexploration.py
That file also contains some code to reproduce the found bugs, and ways used to categorise all the bugs found during the experiments for CP24
That was done dynamically and is out of scope of the 2024 paper, so this code can not be used as is.

Commandline usage:
when measuring code coverage, first set the environment variable COVERAGE_FILE, as to be able to compare multiple files.
> export COVERAGE_FILE='.coverage_metamorphic-ortools5iter10hrs'

To rerun the experiments form the 2024 paper:
run the metamorphic test with the specified solver, number of mutations per input model, and time to run in hours.
> nohup coverage run metamorphic_tests.py ortools 10 5 >/dev/null 2>&1 &
(for each verification method, number of mutations(n=1, 2, 5, 10) and solver = {ortools, minizinc) )

Every verification method has it's own python executable that works in a similar manner:


note that the experiments other than the one testing the number of mutations always use 5 mutations, so this 3rd parameter can be left out.
