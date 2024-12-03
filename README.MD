
## Usages guide
### Installation
```bash
git clone https://github.com/CPMpy/fuzz-test.git # Clone the git repo
pip install -r requirements.txt # install the necessary packages 
```
### Usage
#### fuzz_test
Run the fuzz_test.py (with or without parameters)
The fuzz_test has 5 different verifiers:
- metamorphic_verifier.py : Satisifiability check
- equivalance_verifier.py : All-Solutions check
- model_counting_verifier.py: Solution count check
- optimization_verifier.py: Optimisation check
- solution_check_verifier.py: 1-Solution check

How does fuzz_test works? It works as follows: we take a random verifier, a random model, and random mutations on the chosen model. We will then run the chosen verifier on the chosen model with the random mutations and see if the checks hold. If the checks dont hold or an other error/bug occured the application will generate a log for each error separately in the output directory (can be set in the parameters). The logs will contain more details on how and why the error/bug occured.

#### prameters
fuzz_test.py takes multiple optional parameters:
 - -s --solver : The solver to use to do the fuzz testing, these are all the solvers that are also availabe in cpmpy
 - -m --models : The directory were the models are located that you want to test, note the models diretory needs to have the following structure: 
 
      ```
      ├──  models
        ├──  pickle_examples
          ├── sat
            ├──  model1.pickle
            ├──  model2.pickle
            ├──  ...
          ├── optimization
            ├──  model1.pickle
            ├──  model2.pickle
            ├──  ...
          ├──  ...
        ├──  ...
    ```
 - -o --output-dir: the directory were to store the outputs
 - -g --skip-global-constraints: an boolean value to determine if the global contraints will be skipped during the testing or not
 - --max-failed-tests: a positive int number to determine if the application needs to quit testing if it reached X amount of failed tests (default there is no limit)
 - --max-minutes: a positive int number to determine if the application needs to quit testing if it takes longer then X minutes (by default the tests run indefinitely). If the max-failed-tests was reached before max minutes the application will quit.
 - -mpm --mutations-per-model: the amount of mutations to execute on each model
 - -p --amount-of-processes: the amount of processes that will be used to run the tests

#### example
```bash
py fuzz_test.py # it will run with the default parameters, it will take the models from the /models dir and store the output in the /output dir

py fuzz_test.py --max-minutes 10 # the tests will run for 10 minutes and then the application will quit

py fuzz_test.py --max-failed-tests 5 # The test will run until 5 tests failed, then the application quits

py fuzz_test.py --max-minutes 15 --max-failed-tests 100 # the tests will run until 100 tests failed or until 15 minutes have passed
```

## Rerun bugs
The fuzz_test_rerunner.py script allows you to reproduce and debug errors that were found during fuzz testing. When the fuzz_test.py finds errors, it saves them as pickle files in the output directory. The rerunner helps you investigate these errors by:

1. Loading and replaying the exact sequence of mutations that caused the error
2. Check if bugs persist on other cpmpy branches.
3. Allowing you to debug the specific conditions that triggered the failure

To use the rerunner:
#### Parameters
The rerunner script accepts the following parameters:
- `-m, --failed_model_file`: Path to a single pickle file or directory containing multiple pickle files (defaults to 'output')
- `-o, --output-dir`: Directory to store output (will be created if it doesn't exist, defaults to "bug_output")
- `-p, --amount-of-processes`: Number of processes to use for running tests (defaults to CPU count - 1)
- `-e, --elaborate`: Enable elaborate printing to show filenames of re-run errors (defaults to False)
- `-r, --remove`: Remove fixed error files
- `-M, --move-dir`: Directory to move fixed error files to

#### output
There will be output printed telling you how many tests still failed, and how many no longer failed.
You have the option of (re)moving files that no longer fail.

## Model Generator
The model_generator.py script extracts solvable test models from CPMpy's unittest suite. This provides a diverse set of real-world models that can be used as input for fuzz testing.

#### Parameters
The model generator accepts the following parameters:
- `-c, --cpmpy-dir`: The directory where CPMpy is located (required)
- `-o, --output-dir`: Directory to store the extracted models (defaults to 'solved_models', will be created if it doesn't exist)

The script works by:
1. Running all unittest cases from the specified CPMpy installation
2. Capturing models that are solved during test execution
3. Saving these models as pickle files in the output directory

These extracted models serve as the starting point for mutation-based fuzz testing, ensuring that the initial models are valid and solvable before mutations are applied.


## Acknowledgments

Part of the development received funding through Prof. Tias Guns his European Research Council (ERC) Consolidator grant, under the European Union’s Horizon 2020 research and innovation programme (grant agreement No 101002802, [CHAT-Opt](https://people.cs.kuleuven.be/~tias.guns/chat-opt.html)).

You can cite the HURRICANE as follows: "Vanroose, W., Bleukx, I., Devriendt, J., Tsouros, D., Verhaeghe, H., Guns, T. (2024). Mutational Fuzz Testing for Constraint Modeling Systems. Thirtieth International Conference on Principles and Practice of Constraint Programming, CP 2024."

```
@inproceedings{vanroose2024,
    title={Mutational Fuzz Testing for Constraint Modeling Systems.},
    author={Wout Vanroose, Ignace Bleukx, Jo Devriendt, Dimos Tsouros, Hélène Verhaeghe, and Tias Guns},
    booktitle={Thirtieth International Conference on Principles and Practice of Constraint Programming (CP 2024)},
    year={2024}
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