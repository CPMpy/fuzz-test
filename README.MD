# Fuzz Testing CPMpy

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
- metamorphic_tests.py : Satisifiability check
- equivalence check.py : All-Solutions check
- model_counting.py    : Solution count check
- optimization.py      : Optimisation check
- solution_check.py    : 1-Solution check

note that the experiments other than the one testing the number of mutations always use 5 mutations, so this 3rd parameter can be left out.

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