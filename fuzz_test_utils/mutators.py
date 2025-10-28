import copy
import random

import numpy as np
from cpmpy.expressions.globalfunctions import GlobalFunction, Abs, Minimum, Maximum, Element, Count, Among, NValue, \
    NValueExcept
from cpmpy.transformations.negation import push_down_negation
from cpmpy.transformations.to_cnf import flat2cnf

from cpmpy import intvar, Model
from cpmpy.expressions.core import Operator, Comparison, BoolVal, Expression
from cpmpy.transformations.decompose_global import decompose_in_tree
from cpmpy.transformations.get_variables import get_variables
from cpmpy.transformations.linearize import linearize_constraint, only_positive_bv, canonical_comparison
from cpmpy.expressions.utils import is_boolexpr, is_any_list, is_bool, is_int, is_num
from cpmpy.transformations.flatten_model import flatten_constraint, normalized_boolexpr, normalized_numexpr, \
    flatten_objective, __is_flat_var
from cpmpy.transformations.normalize import toplevel_list, simplify_boolean
from cpmpy.transformations.reification import only_bv_reifies, reify_rewrite
from cpmpy.transformations.comparison import only_numexpr_equality
from cpmpy.expressions.globalconstraints import Xor, AllDifferent, AllDifferentExceptN, AllEqual, AllEqualExceptN, \
    Circuit, Inverse, Table, NegativeTable, IfThenElse, InDomain, Cumulative, Precedence, NoOverlap, \
    GlobalCardinalityCount, Increasing, Decreasing, IncreasingStrict, DecreasingStrict, LexLess, LexLessEq, \
    LexChainLess, LexChainLessEq, GlobalConstraint
# from cpmpy.expressions.globalfunctions import Abs, Mimimum(GlobalFunction), Maximum
from cpmpy.expressions.variables import boolvar, _IntVarImpl, NDVarArray


class Function:
    def __init__(self, name, func, type_: str, int_args: int, bool_args: int,
                 bool_return: bool | None,
                 min_args: int = None,
                 max_args: int = None):
        """
        type        = string that describes the type of function it is
        int_args    = the amount of args of type int it requires
        bool_args   = the amount of args of type bool it requires
        bool_return = a boolean representing whether it returns a boolean (False means int return type, None means it can be either)
        min_args    = the minimum amount of args the function takes
        max_args    = the maximum amount of args the function takes
        """
        self.name = name
        self.func = func
        self.type = type_
        self.int_args = int_args
        self.bool_args = bool_args
        self.bool_return = bool_return
        self.min_args = min_args
        self.max_args = max_args

    def __repr__(self):
        return (f"Operation({self.name}, {self.type}, {self.int_args}, {self.bool_args}, "
                f"{self.bool_return}, min_args={self.min_args}, max_args={self.max_args})")


'''TRUTH TABLE BASED MORPHS'''
def not_morph(cons):
    con = random.choice(cons)
    ncon = ~con
    return [~ncon]


def xor_morph(cons):
    '''morph two constraints with XOR'''
    con1, con2 = random.choices(cons, k=2)
    # add a random option as per xor truth table
    return [random.choice((
        Xor([con1, ~con2]),
        Xor([~con1, con2]),
        ~Xor([~con1, ~con2]),
        ~Xor([con1, con2])))]


def and_morph(cons):
    '''morph two constraints with AND'''
    con1, con2 = random.choices(cons, k=2)
    return [random.choice((
        ~((con1) & (~con2)),
        ~((~con1) & (~con2)),
        ~((~con1) & (con2)),
        ((con1) & (con2))))]


def or_morph(cons):
    '''morph two constraints with OR'''
    con1, con2 = random.choices(cons, k=2)
    # add all options as per xor truth table
    return [random.choice((
        ((con1) | (~con2)),
        ~((~con1) | (~con2)),
        ((~con1) | (con2)),
        ((con1) | (con2))))]


def implies_morph(cons):
    '''morph two constraints with ->'''
    con1, con2 = random.choices(cons, k=2)
    try:
        # add all options as per xor truth table
        return [random.choice((
            ~((con1).implies(~con2)),
            ((~con1).implies(~con2)),
            ((~con1).implies(con2)),
            ((con1).implies(con2)),
            ~((con2).implies(~con1)),
            ((~con2).implies(~con1)),
            ((~con2).implies(con1)),
            ((con2).implies(con1))))]
    except Exception as e:
        raise MetamorphicError(implies_morph, cons, e)


'''CPMPY-TRANSFORMATION MORPHS'''


def canonical_comparison_morph(cons):
    n = random.randint(1, len(cons))
    randcons = random.choices(cons, k=n)
    try:
        return canonical_comparison(cons)
    except Exception as e:
        raise MetamorphicError(canonical_comparison, cons, e)


def flatten_morph(cons, flatten_all=False):
    if flatten_all is False:
        n = random.randint(1, len(cons))
        randcons = random.choices(cons, k=n)
    else:
        randcons = cons
    try:
        return flatten_constraint(randcons)
    except Exception as e:
        raise MetamorphicError(flatten_constraint, randcons, e)


def simplify_boolean_morph(cons):
    try:
        return simplify_boolean(cons)
    except Exception as e:
        raise MetamorphicError(simplify_boolean, cons, e)


def only_numexpr_equality_morph(cons, supported=frozenset()):
    n = random.randint(1, len(cons))
    randcons = random.choices(cons, k=n)
    flatcons = flatten_morph(randcons, flatten_all=True)  # only_numexpr_equality requires flat constraints
    try:
        newcons = only_numexpr_equality(flatcons, supported=supported)
        return newcons
    except Exception as e:
        raise MetamorphicError(only_numexpr_equality, flatcons, e)


def normalized_boolexpr_morph(cons):
    '''normalized_boolexpr only gets called within other transformations, so can probably safely be omitted from our test.
    Keeping it in gives unwanted results, for example crashing on flatvar input'''
    randcon = random.choice(cons)
    if not __is_flat_var(randcon):
        try:
            con, newcons = normalized_boolexpr(randcon)
            return newcons + [con]
        except Exception as e:
            raise MetamorphicError(normalized_boolexpr, randcon, e)
    else:
        return cons


def normalized_numexpr_morph(const):
    try:
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        firstcon = None
        for i, con in enumerate(cons):
            res = pickaritmetic(con, log=[i])
            if res != []:
                firstcon = random.choice(res)
                break  # numexpr found
        if firstcon is None:
            # no numexpressions found but still call the function to test on all inputs
            randcon = random.choice(cons)
            try:
                con, newcons = normalized_numexpr(randcon)
                return newcons + [con]
            except Exception as e:
                raise MetamorphicError(normalized_numexpr, randcon, e)
        else:
            # get the numexpr
            arg = cons[firstcon[0]]
            newfirst = arg
            for i in firstcon[1:]:
                arg = arg.args[i]
            firstexpr = arg
            try:
                con, newcons = normalized_numexpr(firstexpr)
            except Exception as e:
                raise MetamorphicError(normalized_numexpr, firstexpr, e)

            # make the new constraint (newfirst)
            arg = newfirst
            c = 1
            for i in firstcon[1:]:
                c += 1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        listargs = list(arg.args)
                        listargs[i] = con
                        arg.args = tuple(listargs)
                    else:
                        arg.args[i] = con
                else:
                    arg = arg.args[i]

            return [newfirst] + newcons
    except Exception as e:
        raise MetamorphicError(normalized_numexpr_morph, cons, e)


def linearize_constraint_morph(cons, linearize_all=False, supported={}):
    if linearize_all:
        randcons = cons
    else:
        n = random.randint(1, len(cons))
        randcons = random.choices(cons, k=n)

    # only apply linearize after only_bv_reifies
    decomcons = decompose_in_tree_morph(randcons, decompose_all=True, supported=supported)
    flatcons = only_bv_reifies_morph(decomcons, morph_all=True)
    try:
        return linearize_constraint(flatcons, supported={'mul'})
    except Exception as e:
        raise MetamorphicError(linearize_constraint, flatcons, e)


def reify_rewrite_morph(cons):
    n = random.randint(1, len(cons))
    randcons = random.choices(cons, k=n)
    decomps = decompose_in_tree_morph(randcons, decompose_all=True)
    flatcons = flatten_morph(decomps, flatten_all=True)
    try:
        return reify_rewrite(flatcons)
    except Exception as e:
        raise MetamorphicError(reify_rewrite, flatcons, e)


def push_down_negation_morph(cons):
    try:
        return push_down_negation(cons)
    except Exception as e:
        raise MetamorphicError(push_down_negation, cons, e)


def flatten_objective_morph(objective):
    '''Only for optimization problems, pass the objective function, not constraints'''
    try:
        return flatten_objective(objective)
    except Exception as e:
        raise MetamorphicError(flatten_objective, objective, e)


def decompose_in_tree_morph(cons, decompose_all=False, supported={}):
    try:
        return decompose_in_tree(cons, supported=supported)
    except Exception as e:
        raise MetamorphicError(decompose_in_tree, cons, e)


def only_bv_reifies_morph(cons, morph_all=True):
    if morph_all:
        randcons = cons
    else:
        n = random.randint(1, len(cons))
        randcons = random.choices(cons, k=n)
    flatcons = flatten_morph(randcons, flatten_all=True)
    try:
        return only_bv_reifies(flatcons)
    except Exception as e:
        raise MetamorphicError(only_bv_reifies, flatcons, e)


def only_positive_bv_morph(cons):
    lincons = linearize_constraint_morph(cons, linearize_all=True, supported={})
    try:
        return only_positive_bv(lincons)
    except Exception as e:
        raise MetamorphicError(only_positive_bv, lincons, e)


def flat2cnf_morph(cons):
    # flatcons = flatten_morph(og_cons,flatten_all=True)
    onlycons = only_bv_reifies_morph(cons, morph_all=True)
    try:
        return flat2cnf(onlycons)
    except Exception as e:
        raise MetamorphicError(flat2cnf, onlycons, e)


def toplevel_list_morph(cons):
    try:
        return toplevel_list(cons)
    except Exception as e:
        raise MetamorphicError(toplevel_list, cons, e)


def add_solution(cons):
    vars = get_variables(cons)
    try:
        Model(cons).solve()
    except Exception as e:
        raise MetamorphicError(add_solution, cons, e)
    return [var == var.value() for var in vars if var.value() is not None]


def semanticFusion(const):
    try:
        firstcon = None
        secondcon = None
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        for i, con in enumerate(cons):
            res = pickaritmetic(con, log=[i])
            if res != []:
                if firstcon == None:
                    firstcon = random.choice(res)
                elif secondcon == None:
                    secondcon = random.choice(res)
                    break  # stop when 2 constraints found. still random because og_cons are shuffled

        if secondcon != None:
            # two constraints with aritmetic expressions found, perform semantic fusion on them
            # get the expressions to fuse
            arg = cons[firstcon[0]]
            newfirst = copy.deepcopy(arg)
            count = 0
            for i in firstcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg, 'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(firstcon) > count + 1:
                            if firstcon[count + 1] == 1:
                                return []  # we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            firstexpr = arg

            arg = cons[secondcon[0]]
            newsecond = arg
            count = 0
            for i in secondcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg, 'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(secondcon) > count + 1:
                            if secondcon[count + 1] == 1:
                                return []  # we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            secondexpr = arg

            lb, ub = Operator('sum', [firstexpr, secondexpr]).get_bounds()
            z = intvar(lb, ub)
            firstexpr, secondexpr = z - secondexpr, z - firstexpr

            # make the new constraints
            arg = newfirst
            c = 1
            firststr = str(firstexpr)
            for i in firstcon[1:]:
                if str(arg) in firststr:
                    return []  # cyclical
                c += 1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = firstexpr
                else:
                    arg = arg.args[i]

            arg = newsecond
            c = 1
            secondstr = str(secondexpr)
            for i in secondcon[1:]:
                if str(arg) in secondstr:
                    return []  # cyclical
                c += 1
                if c == len(secondcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = secondexpr
                else:
                    arg = arg.args[i]

            return [newfirst, newsecond]

        else:
            # no expressions found to fuse
            return []

    except Exception as e:
        raise MetamorphicError(semanticFusion, cons, e)


def semanticFusionMinus(const):
    try:
        firstcon = None
        secondcon = None
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        for i, con in enumerate(cons):
            res = pickaritmetic(con, log=[i])
            if res != []:
                if firstcon == None:
                    firstcon = random.choice(res)
                elif secondcon == None:
                    secondcon = random.choice(res)
                    break  # stop when 2 constraints found. still random because og_cons are shuffled

        if secondcon != None:
            # two constraints with aritmetic expressions found, perform semantic fusion on them
            # get the expressions to fuse
            arg = cons[firstcon[0]]
            newfirst = copy.deepcopy(arg)
            count = 0
            for i in firstcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg, 'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(firstcon) > count + 1:
                            if firstcon[count + 1] == 1:
                                return []  # we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            firstexpr = arg

            arg = cons[secondcon[0]]
            newsecond = arg
            count = 0
            for i in secondcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg, 'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(secondcon) > count + 1:
                            if secondcon[count + 1] == 1:
                                return []  # we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            secondexpr = arg

            lb, ub = Operator('sub', [firstexpr, secondexpr]).get_bounds()
            z = intvar(lb, ub)
            firstexpr, secondexpr = z + secondexpr, firstexpr - z

            # make the new constraints
            arg = newfirst
            c = 1
            firststr = str(firstexpr)
            for i in firstcon[1:]:
                if str(arg) in firststr:
                    return []  # cyclical
                c += 1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = firstexpr
                else:
                    arg = arg.args[i]

            arg = newsecond
            c = 1
            secondstr = str(secondexpr)
            for i in secondcon[1:]:
                if str(arg) in secondstr:
                    return []  # cyclical
                c += 1
                if c == len(secondcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = secondexpr
                else:
                    arg = arg.args[i]

            return [newfirst, newsecond]

        else:
            # no expressions found to fuse
            return []

    except Exception as e:
        raise MetamorphicError(semanticFusionMinus, cons, e)


def semanticFusionwsum(const):
    try:
        firstcon = None
        secondcon = None
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        for i, con in enumerate(cons):
            res = pickaritmetic(con, log=[i])
            if res != []:
                if firstcon == None:
                    firstcon = random.choice(res)
                elif secondcon == None:
                    secondcon = random.choice(res)
                    break  # stop when 2 constraints found. still random because og_cons are shuffled

        if secondcon != None:
            # two constraints with aritmetic expressions found, perform semantic fusion on them
            # get the expressions to fuse
            arg = cons[firstcon[0]]
            newfirst = copy.deepcopy(arg)
            count = 0
            for i in firstcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg, 'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(firstcon) > count + 1:
                            if firstcon[count + 1] == 1:
                                return []  # we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            firstexpr = arg

            arg = cons[secondcon[0]]
            # newsecond = copy.deepcopy(arg)
            newsecond = (arg)
            count = 0
            for i in secondcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg, 'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(secondcon) > count + 1:
                            if secondcon[count + 1] == 1:
                                return []  # we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            secondexpr = arg

            l = random.randint(1, 10)
            n = random.randint(1, 10)
            m = random.randint(1, 10)
            lb, ub = Operator('wsum', [[l, m, n], [firstexpr, secondexpr, 1]]).get_bounds()
            z = intvar(lb, ub)
            firstexpr, secondexpr = Operator('wsum', [[1, -m, -n], [z, secondexpr, 1]]) / l, Operator('wsum',
                                                                                                      [[1, -l, -n],
                                                                                                       [z, firstexpr,
                                                                                                        1]]) / m
            # make the new constraints
            arg = newfirst
            c = 1
            firststr = str(firstexpr)
            for i in firstcon[1:]:
                if str(arg) in firststr:
                    return []  # cyclical
                c += 1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = firstexpr
                else:
                    arg = arg.args[i]

            arg = newsecond
            c = 1
            secondstr = str(secondexpr)
            for i in secondcon[1:]:
                if str(arg) in secondstr:
                    return []  # cyclical
                c += 1
                if c == len(secondcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = secondexpr
                else:
                    arg = arg.args[i]

            return [newfirst, newsecond]

        else:
            # no expressions found to fuse
            return []

    except Exception as e:
        raise MetamorphicError(semanticFusionwsum, cons, e)


def semanticFusionCountingwsum(const):
    try:
        firstcon = None
        secondcon = None
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        for i, con in enumerate(cons):
            res = pickaritmetic(con, log=[i])
            if res != []:
                if firstcon == None:
                    firstcon = random.choice(res)
                elif secondcon == None:
                    secondcon = random.choice(res)
                    break  # stop when 2 constraints found. still random because og_cons are shuffled

        if secondcon != None:
            # two constraints with aritmetic expressions found, perform semantic fusion on them
            # get the expressions to fuse
            arg = cons[firstcon[0]]
            newfirst = copy.deepcopy(arg)
            count = 0
            for i in firstcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg, 'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(firstcon) > count + 1:
                            if firstcon[count + 1] == 1:
                                return []  # we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            firstexpr = arg

            arg = cons[secondcon[0]]
            newsecond = arg
            count = 0
            for i in secondcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg, 'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(secondcon) > count + 1:
                            if secondcon[count + 1] == 1:
                                return []  # we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            secondexpr = arg

            l = random.randint(1, 10)
            n = random.randint(1, 10)
            m = random.randint(1, 10)
            lb, ub = Operator('wsum', [[l, m, n], [firstexpr, secondexpr, 1]]).get_bounds()
            z = intvar(lb, ub)
            thirdcon = z == Operator('wsum', [[l, m, n], [firstexpr, secondexpr, 1]])
            firstexpr, secondexpr = Operator('wsum', [[1, -m, -n], [z, secondexpr, 1]]) / l, Operator('wsum',
                                                                                                      [[1, -l, -n],
                                                                                                       [z, firstexpr,
                                                                                                        1]]) / m

            # make the new constraints
            arg = newfirst
            c = 1
            firststr = str(firstexpr)
            for i in firstcon[1:]:
                if str(arg) in firststr:
                    return []  # cyclical
                c += 1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = firstexpr
                else:
                    arg = arg.args[i]

            arg = newsecond
            c = 1
            secondstr = str(secondexpr)
            for i in secondcon[1:]:
                if str(arg) in secondstr:
                    return []  # cyclical
                c += 1
                if c == len(secondcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = secondexpr
                else:
                    arg = arg.args[i]

            return [newfirst, newsecond, thirdcon]

        else:
            # no expressions found to fuse
            return []

    except Exception as e:
        raise MetamorphicError(semanticFusionCountingwsum, cons, e)


def semanticFusionCounting(const):
    try:
        firstcon = None
        secondcon = None
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        for i, con in enumerate(cons):
            res = pickaritmetic(con, log=[i])
            if res != []:
                if firstcon == None:
                    firstcon = random.choice(res)
                elif secondcon == None:
                    secondcon = random.choice(res)
                    break  # stop when 2 constraints found. still random because og_cons are shuffled

        if secondcon != None:
            # two constraints with aritmetic expressions found, perform semantic fusion on them
            # get the expressions to fuse
            arg = cons[firstcon[0]]
            newfirst = copy.deepcopy(arg)
            count = 0
            for i in firstcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg, 'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(firstcon) > count + 1:
                            if firstcon[count + 1] == 1:
                                return []  # we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            firstexpr = arg

            arg = cons[secondcon[0]]
            newsecond = arg
            count = 0
            for i in secondcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg, 'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(secondcon) > count + 1:
                            if secondcon[count + 1] == 1:
                                return []  # we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            secondexpr = arg

            lb, ub = Operator('sum', [firstexpr, secondexpr]).get_bounds()
            z = intvar(lb, ub)
            firstexpr, secondexpr = z - secondexpr, z - firstexpr
            thirdcon = z == firstexpr + secondexpr

            # make the new constraints
            arg = newfirst
            c = 1
            firststr = str(firstexpr)
            for i in firstcon[1:]:
                if str(arg) in firststr:
                    return []  # cyclical
                c += 1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = firstexpr
                else:
                    arg = arg.args[i]

            arg = newsecond
            c = 1
            secondstr = str(secondexpr)
            for i in secondcon[1:]:
                if str(arg) in secondstr:
                    return []  # cyclical
                c += 1
                if c == len(secondcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = secondexpr
                else:
                    arg = arg.args[i]

            return [newfirst, newsecond, thirdcon]

        else:
            # no expressions found to fuse
            return []

    except Exception as e:
        raise MetamorphicError(semanticFusionCounting, cons, e)


def semanticFusionCountingMinus(const):
    try:
        firstcon = None
        secondcon = None
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        for i, con in enumerate(cons):
            res = pickaritmetic(con, log=[i])
            if res != []:
                if firstcon == None:
                    firstcon = random.choice(res)
                elif secondcon == None:
                    secondcon = random.choice(res)
                    break  # stop when 2 constraints found. still random because og_cons are shuffled

        if secondcon != None:
            # two constraints with aritmetic expressions found, perform semantic fusion on them
            # get the expressions to fuse
            arg = cons[firstcon[0]]
            newfirst = copy.deepcopy(arg)
            count = 0
            for i in firstcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg, 'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(firstcon) > count + 1:
                            if firstcon[count + 1] == 1:
                                return []  # we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            firstexpr = arg

            arg = cons[secondcon[0]]
            newsecond = arg
            count = 0
            for i in secondcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg, 'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(secondcon) > count + 1:
                            if secondcon[count + 1] == 1:
                                return []  # we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            secondexpr = arg

            lb, ub = Operator('sub', [firstexpr, secondexpr]).get_bounds()
            z = intvar(lb, ub)
            firstexpr, secondexpr = z + secondexpr, firstexpr - z
            thirdcon = z == firstexpr - secondexpr
            # make the new constraints
            arg = newfirst
            c = 1
            firststr = str(firstexpr)
            for i in firstcon[1:]:
                if str(arg) in firststr:
                    return []  # cyclical
                c += 1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = firstexpr
                else:
                    arg = arg.args[i]

            arg = newsecond
            c = 1
            secondstr = str(secondexpr)
            for i in secondcon[1:]:
                if str(arg) in secondstr:
                    return []  # cyclical
                c += 1
                if c == len(secondcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = secondexpr
                else:
                    arg = arg.args[i]

            return [newfirst, newsecond, thirdcon]

        else:
            # no expressions found to fuse
            return []

    except Exception as e:
        raise MetamorphicError(semanticFusionCountingMinus, cons, e)


def aritmetic_comparison_morph(const):
    try:
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        firstcon = None
        for i, con in enumerate(cons):
            res = pickaritmeticComparison(con, log=[i])
            if res != []:
                firstcon = random.choice(res)
                break  # numexpr found
        if firstcon is None:
            # no arithmetic comparisons found
            return []
        else:
            # get the expression
            arg = cons[firstcon[0]]
            newfirst = arg
            for i in firstcon[1:]:
                arg = arg.args[i]
            firstexpr = arg
            try:
                lhs = firstexpr.args[0]
                rhs = firstexpr.args[1]
                lhs1 = lhs * 7
                rhs1 = rhs * 7
                lhs2 = lhs + 7
                rhs2 = rhs + 7
                lhs3 = lhs - 7
                rhs3 = rhs - 7
                lhs, rhs = random.choice([(lhs3, rhs3), (lhs2, rhs2), (lhs1, rhs1)])
                newcon = Comparison(name=firstexpr.name, left=lhs, right=rhs)
            except Exception as e:
                raise MetamorphicError(aritmetic_comparison_morph, firstexpr, e)

            # make the new constraint (newfirst)
            arg = newfirst
            if len(firstcon) == 1:  # toplevel comparison
                return [newcon]
            c = 1
            for i in firstcon[1:]:
                c += 1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        listargs = list(arg.args)
                        listargs[i] = newcon
                        arg.args = tuple(listargs)
                    else:
                        arg.args[i] = newcon
                else:
                    arg = arg.args[i]

            return [newfirst]
    except Exception as e:
        raise MetamorphicError(aritmetic_comparison_morph, cons, e)


def type_aware_operator_replacement(constraints: list):
    """
    Replaces a random operator of a random constraint from a list of given constraints.
    IMPORTANT: This can change satisfiability of the constraint! Only to be used with verifiers that allow this!
            This means it returns a list of ALL constraints and has to be handled accordingly in the 'generate_mutations'
            function to swap out the constraints instead of adding them.

    ~ Parameters:
        - constraints: a list of all the constraints to possibly be mutated
    ~ Return:
        - final_cons: a list of the same constraints where one constraint has a mutated operator

    Types of operators ('...' means the amount of arguments is variable):
        - Int,  Bool    -> Bool :  ==  !=  <   <=  >   >=
        - Bool,  Int    -> Bool :  ==  !=  <   <=  >   >=
        - Int,  Int     -> Bool :  ==  !=  <   <=  >   >=
        - [Bool, Bool]  -> Bool :  and or  ->
        - [Bool, ...]   -> Bool :  and or
        - [Bool]        -> Bool :  not
        - Int,  Int     -> Int  :  sum sub mul div mod pow (IMPORTANT: div mod gives problems with domains containing 0, pow with domains containing negative numbers)
        - [Int, ...]    -> Int  :  sum
        - [Int]         -> Int  :  -
        - [Int, ...] [Int, ...] (arrays of same len) -> Int  :  wsum
    """
    try:
        final_cons = copy.deepcopy(constraints)
        # pick a random constraint and calculate whether they have a mutable expression until they do
        candidates = []
        for item in constraints:
            if not any(item is cand for cand in candidates):
                candidates.append(item)
        # candidates = list(set(constraints))  # does not work with NDVarArray
        random.shuffle(candidates)
        for con in candidates:
            exprs = get_all_mutable_op_exprs(con)  # e.g. for (x + y) // z > 0. The tree goes >(0, //(+(x,y), z))
                                                    # which means either >, // or + can get mutated
            if exprs:
                break
        else:  # In case there isn't any mutable expression in any constraint
            return final_cons

        # Remove the constraint from the constraints
        final_cons.remove(con)

        # Choose an expression to change
        expr = random.choice(exprs)

        # Mutate this expression (= change the operator)
        mutate_op_expression(expr, con)

        # Add the changed constraint back
        final_cons.append(con)
        return final_cons

    except Exception as e:
        raise Exception(e)


def mutate_op_expression(expr: Expression, con: Expression):
    """
    Mutates the constraint containing the expression by mutating said expression.
    Only to be called when the expression is known to be in the constraint.

    ~ Parameters:
        - expr: the expression that will be mutated
        - con: the constraint containing the expression
    ~ No return. Mutates the constraint!
    """
    # TODO: other types of functions should also be added (e.g. global constraints/functions)
    # Types that can be converted into each-other
    comparisons = {'==', '!=', '<', '<=', '>', '>='}
    int_ops = {'sum', 'sub', 'mul',
               'pow', 'mod', 'div'}
    logic_ops = {'and', 'or', '->'}
    logic_ops_inf_args = {'and', 'or'}
    if expr == con:  # Found the expression to mutate
        # Determine the type of the operator
        if expr.name in comparisons:  # a, b -> Bool (Comparison() always has two arguments)
            possible_replacements = comparisons - {expr.name}
        elif expr.name in int_ops and len(expr.args) == 2:  # a, a -> Int
            possible_replacements = int_ops - {expr.name}
        elif expr.name in logic_ops and len(expr.args) == 2:  # [Bool, Bool] -> Bool
            possible_replacements = logic_ops - {expr.name}
        elif expr.name in logic_ops_inf_args:  # [Bool, ...] -> Bool
            possible_replacements = logic_ops_inf_args - {expr.name}
        else:
            raise ValueError(f"Unknown operator type: {expr.name}. (You should not be able to get here)")

        new_operator = random.choice(list(possible_replacements))
        expr.name = new_operator # Mutate expression by changing its name
        return

    # Recursively search for the expression in arguments
    if hasattr(con, "args"):
        for arg in con.args:
            mutate_op_expression(expr, arg)
            return


def get_all_mutable_op_exprs(con: Expression):
    """
    Returns a list of all expressions inside the given constraint of which the
    operator can be mutated into another one.

    ~ Parameters:
        - con: a single constraint, possibly containing multiple expressions
    ~ Return:
        - mutable_exprs: all expressions in the constraint that can be mutated
    """
    # TODO: other types of functions should also be added (e.g. global constraints/functions)
    comparisons = {'==', '!=', '<', '<=', '>', '>='}
    int_ops = {'sum', 'sub', 'mul', 'div', 'mod', 'pow'}
    logic_ops = {'and', 'or', '->'}
    logic_ops_inf_args = {'and', 'or'}
    mutable_exprs = []
    for expr in get_all_op_exprs(con):
        if expr.name in comparisons:  # a, b -> Bool (Comparison() always has two arguments)
            mutable_exprs.append(expr)
        elif expr.name in int_ops and len(expr.args) == 2:  # a, b -> Int
            mutable_exprs.append(expr)
        elif expr.name in logic_ops and len(expr.args) == 2:  # [Bool, Bool] -> Bool
            mutable_exprs.append(expr)
        elif expr.name in logic_ops_inf_args:  # [Bool, ...] -> Bool
            mutable_exprs.append(expr)
    return mutable_exprs


def get_all_op_exprs(con: Expression):
    """
    Helper function to get all expressions WITH an operator in a given constraint
    """
    # TODO: other types of functions should also be added (e.g. global constraints/functions)
    if type(con) in {Comparison, Operator}:
        return sum((get_all_op_exprs(arg) for arg in con.args), []) + [con]  # All subexpressions + current expression
    else:
        return []


def get_all_non_op_exprs(con: Expression):
    """
    Helper function to get all expressions WITHOUT an operator in a given constraint
    """
    # TODO: other types of functions should also be added (e.g. global constraints/functions)
    if hasattr(con, 'args') and not isinstance(con, NDVarArray) and con.name != 'boolval':
        return sum((get_all_non_op_exprs(arg) for arg in con.args), [])
    elif isinstance(con, list) or isinstance(con, NDVarArray) or isinstance(con, tuple):
        return sum((get_all_non_op_exprs(e) for e in con), [])
    else:
        return [con]


def get_all_exprs(con: Expression):
    """
    Helper function to get all expressions in a given constraint
    """
    return get_all_op_exprs(con)[::-1] + get_all_non_op_exprs(con)


def get_all_exprs_mult(cons: list):
    """
    Helper function to get all expressions in a given list of constraints (e.g. to get all possible arguments for an
    expression replacement)
    """
    all_exprs = []
    for con in cons:
        all_exprs += get_all_exprs(con)
    return all_exprs


def satisfies_args(func: Function, ints: int, bools: int, constants: int, vars: int, has_bool_return: bool):
    """
    Returns whether a new function of the given type `func` can be created with the given amount of arguments.
    ~ Parameters:
        - `ints`: The amount of integers in the possible arguments (including constants and variables)
        - bools`: The amount of booleans in the possible arguments (including variables)
        - `constants`: The amount of constants in the possible arguments (only numbers)
        - `vars`: The amount of variables in the possible arguments (intvars and boolvars)
        - `has_bool_return`: Indicates whether the return type should be boolean (True) or int (False)
    ~ Returns:
        - True if it is possible to create a new function of given type with the given arguments, False otherwise
    """
    match func.type:
        case 'op' | 'comp':
            match func.name:
                case 'wsum':
                    return constants >= 1 and ints + bools >= func.min_args and has_bool_return == func.bool_return
                case 'pow':
                    return constants >= 1 and ints + bools >= 1 and has_bool_return == func.bool_return
                case _:
                    return ((func.int_args == -1 or func.int_args <= ints + bools) and  # enough int args
                            (func.bool_args == -1 or func.bool_args <= bools) and  # enough bool args
                            (ints + bools >= func.min_args) and  # enough args in general
                            (bools >= func.min_args if func.bool_args == -1 else True) and  # enough bools
                            has_bool_return == func.bool_return)  # return type matches
        case 'gfun':
            match func.name:
                case 'Abs' | 'NValue' | 'Count':
                    return ints + bools >= func.min_args and not has_bool_return
                case 'Minimum' | 'Maximum' | 'Element':  # We make these have only ints, so it always has the same return type
                    return constants >= func.min_args and not has_bool_return
                case 'Among' | 'NValueExcept':
                    return constants >= 1 and ints >= func.min_args - 1 and not has_bool_return
        case 'gcon':
            match func.name:
                case 'GlobalCardinalityCount':
                    return constants >= func.min_args and has_bool_return
                case 'IfThenElse' | 'Xor':
                    return bools >= func.min_args and has_bool_return
                case 'Table' | 'NegativeTable' | 'InDomain':
                    return vars >= 1 and constants >= max(1, func.min_args - 1) and has_bool_return
                case 'LexLess' | 'LexLessEq' | 'LexChainLess' | 'LexChainLessEq':
                    return vars >= func.min_args and has_bool_return
                case 'Circuit' | 'Inverse':
                    return has_bool_return  # No arguments required. We fill in the arrays with logical numbers
                case _:
                    return ints + bools >= func.min_args and has_bool_return


def generate_new_operator(func: Function, ints: list, bools: list, constants: list, variables: list):
    """
    Creates a new function of the given type with the arguments given
    ~ Parameters:
        - `ints`: The integers in the possible arguments (including constants and variables)
        - `bools`: The booleans in the possible arguments (including variables)
        - `constants`: The constants in the possible arguments (only numbers)
        - `variables`: The variables in the possible arguments (intvars and boolvars)
    ~ Returns:
        - A new function with arguments from the given lists (or other arguments based on the Function `func`)
    """
    comb = ints + bools
    match func.type:
        case 'op' | 'comp':
            # Separate logic for wsum and pow
            if func.name == 'wsum':  # (-1, 0, False, 2, max_args, 2)
                amnt_args = random.randint(func.min_args // 2, min(len(constants), func.max_args // 2))
                # First take constants
                constants = random.sample(constants, amnt_args)
                # Then the other expressions
                others = random.sample(comb, amnt_args)
                return Operator(func.name, [constants, others])
            if func.name == 'pow':
                args = random.choice(comb), random.choice(constants)
                return Operator(func.name, args)
            # Logic for all other operators and comparisons is the same
            if func.int_args == -1:
                amnt_args = random.randint(func.min_args, min(len(comb),
                                                              func.max_args))  # Take at least min_args and at most max_args arguments
                args = random.sample(comb, amnt_args)
            elif func.int_args > 0:
                args = random.sample(comb, func.int_args)
            if func.bool_args == -1:
                amnt_args = random.randint(func.min_args, min(len(bools),
                                                              func.max_args))  # Take at least min_args and at most max_args arguments
                args = random.sample(bools, amnt_args)
            elif func.bool_args > 0:
                args = random.sample(bools, func.bool_args)
            if func.type == 'op':
                return Operator(func.name, args)
            if func.type == 'comp':
                return Comparison(func.name, *args)
        case 'gfun':
            match func.name:
                case 'Abs':
                    args = random.choice(comb),
                case 'Minimum' | 'Maximum':
                    amnt_args = random.randint(func.min_args, min(len(constants), func.max_args))
                    args = random.sample(constants, amnt_args),
                case 'Element':
                    amnt_args = random.randint(func.min_args, min(len(constants), func.max_args))
                    first_arg = random.sample(constants, amnt_args)
                    # idx = random.randint(0, amnt_args - 1)
                    constants_filtered = [e for e in constants if (isinstance(e, int) and e <= amnt_args - 1)]  # Make sure you can't take an integer out of bounds
                    idx = random.choice(constants_filtered + variables)
                    args = first_arg, idx
                case 'NValue':
                    amnt_args = random.randint(func.min_args, min(len(comb), func.max_args))
                    args = random.sample(comb, amnt_args),
                case 'Count':
                    amnt_args = random.randint(func.min_args, min(len(comb), func.max_args))
                    first_arg = random.sample(comb, amnt_args - 1)
                    last_arg = random.choice(comb)
                    args = first_arg, last_arg
                case 'Among':
                    amnt_fst_arg = random.randint(func.min_args // 2, min(len(comb), func.max_args // 2))
                    amnt_snd_arg = random.randint(func.min_args // 2, min(len(constants), func.max_args // 2))
                    first_arg = random.sample(comb, amnt_fst_arg)
                    second_arg = random.sample(constants, amnt_snd_arg)
                    args = first_arg, second_arg
                case 'NValueExcept':
                    amnt_fst_arg = random.randint(func.min_args // 2, min(len(comb), func.max_args // 2))
                    first_arg = random.sample(comb, amnt_fst_arg)
                    second_arg = random.choice(constants)
                    args = first_arg, second_arg
            return func.func(*args)
        case 'gcon':
            match func.name:
                case 'AllDifferent' | 'AllEqual' | 'Increasing' | 'Decreasing' | 'IncreasingStrict' | 'DecreasingStrict':
                    amnt_args = random.randint(func.min_args, min(len(comb), func.max_args))
                    args = random.sample(comb, amnt_args)
                case 'AllDifferentExceptN' | 'AllEqualExceptN':
                    amnt_fst_args = random.randint(func.min_args // 2, min(len(comb), func.max_args // 2))
                    amnt_snd_args = random.randint(func.min_args // 2, min(len(comb), func.max_args - amnt_fst_args))
                    args = random.sample(comb, amnt_fst_args), random.sample(comb, amnt_snd_args)
                case 'LexLess' | 'LexLessEq':
                    half_amnt_args = random.randint(func.min_args // 2, min(len(variables), func.max_args // 2))
                    args = random.sample(variables, half_amnt_args), random.sample(variables, half_amnt_args)
                case 'LexChainLess' | 'LexChainLessEq':
                    amnt_fst_args = random.randint(1, min(len(variables), func.max_args // 4))
                    fst_args = random.sample(variables, amnt_fst_args)
                    amnt_snd_args = random.randint(1, func.max_args // 4)  # the amnt of arrays of len of the first one
                    snd_args = [random.sample(variables, amnt_fst_args) for _ in range(amnt_snd_args)]
                    args = [fst_args] + snd_args,
                case 'Circuit':
                    amnt_args = random.randint(func.min_args, func.max_args)
                    args = random.sample(range(amnt_args), amnt_args),
                case 'Inverse':
                    amnt_args = random.randint(func.min_args // 2, func.max_args // 2)
                    args = random.sample(range(amnt_args), amnt_args), random.sample(range(amnt_args), amnt_args)
                case 'IfThenElse':
                    amnt_args = random.randint(func.min_args, min(len(bools), func.max_args))
                    args = random.sample(bools, amnt_args)
                case 'Xor':
                    amnt_args = random.randint(func.min_args, min(len(bools), func.max_args))
                    args = random.sample(bools, amnt_args),
                case 'Table' | 'NegativeTable':
                    amnt_fst_arg = random.randint(1, min(len(variables), len(constants), func.max_args // 4))
                    amnt_snd_args = random.randint(1, min(len(constants),
                                                          func.max_args - amnt_fst_arg) // amnt_fst_arg) * amnt_fst_arg
                    fst_args = random.sample(variables, amnt_fst_arg)
                    snd_args = random.sample(constants, amnt_snd_args)
                    snd_args_transformed = [snd_args[i * amnt_fst_arg:(i + 1) * amnt_fst_arg] for i in
                                            range(int(amnt_snd_args / amnt_fst_arg))]
                    args = fst_args, snd_args_transformed
                case 'InDomain':
                    fst_arg = random.choice(variables)
                    amnt_snd_args = random.randint(func.min_args - 1, min(len(constants), func.max_args - 1))
                    snd_args = random.sample(constants, amnt_snd_args)
                    args = fst_arg, snd_args
                case 'NoOverlap':
                    amnt_args = random.randint(func.min_args, min(len(comb), func.max_args // 3))
                    args = random.sample(comb, amnt_args), random.sample(comb, amnt_args), random.sample(comb,
                                                                                                         amnt_args)
                case 'GlobalCardinalityCount':
                    amnt_fst_args = random.randint(1, min(len(constants), func.max_args - 2))
                    amnt_snd_args = random.randint(1, min(len(constants), (func.max_args - amnt_fst_args) // 2))
                    counts = [random.randint(0, amnt_fst_args) for _ in range(amnt_snd_args)]
                    args = random.sample(constants, amnt_fst_args), counts, random.sample(constants, amnt_snd_args)
                case _:
                    args = []
            return func.func(*args)


def get_operator(args: list, ret_type: str | bool):
    """
    Randomly generates a new Expression that can be created with the given arguments `args` and return type `ret_type`.
    ~ Parameters:
        - `args`: all arguments that should be in the newly generated function.
        - `ret_type`: the return type that the new function should have (usually generated by `get_return_type`).
            There are four options:
            -> 'constant' for numbers only
            -> 'variable' for variables only
            -> True for boolean (including variables)
            -> False for int (including numbers and variables)
    ~ Returns:
        - A new Expression with arguments from the given list and with given return type
    """
    ints = [e for e in args if not (is_boolexpr(e) or isinstance(e, list) or isinstance(e, NDVarArray) or isinstance(e, tuple))]
    bools = [e for e in args if is_boolexpr(e)]
    constants = [e for e in args if isinstance(e, int)]
    variables = get_variables(args)
    if ret_type == 'constant':
        if constants:
            return random.choice(constants)  # Some expressions can't be replaced by functions
        intvars = [e for e in variables if not (is_boolexpr(e) or isinstance(e, list) or isinstance(e, NDVarArray) or isinstance(e, tuple))]
        if intvars:
            return random.choice(intvars)
    if ret_type == 'variable' and variables:
        return random.choice(variables)  # Some expressions can't be replaced by functions
    ints_cnt = len(ints)
    bools_cnt = len(bools)
    constants_cnt = len(constants)
    vars_cnt = len(variables)
    max_args = 12  # TODO: parametriseer?

    # Operators:
    ops = {
        # name: (type, int_args, bool_args, bool_return, min_args, max_args)       .._args -1 = n-ary, min 2
        name: Function(name, name, *attrs)
        for name, attrs in {
            'and': ('op', 0, -1, True, 2, max_args),
            'or': ('op', 0, -1, True, 2, max_args),
            '->': ('op', 0, 2, True, 2, 2),
            'not': ('op', 0, 1, True, 1, 1),
            'sum': ('op', -1, 0, False, 2, max_args),
            'wsum': ('op', -1, 0, False, 2, max_args),
            'sub': ('op', 2, 0, False, 2, 2),
            'mul': ('op', 2, 0, False, 2, 2),
            'div': ('op', 2, 0, False, 2, 2),
            'mod': ('op', 2, 0, False, 2, 2),
            'pow': ('op', 2, 0, False, 2, 2),
            '-': ('op', 1, 0, False, 1, 1),
        }.items()
    }
    # Comparisons
    comps = {
        # name: (type, int_args, bool_args, bool_return)       .._args -1 = n-ary, min 2
        name: Function(name, name, *attrs)
        for name, attrs in {
            '==': ('comp', 2, 0, True, 2, 2),
            '!=': ('comp', 2, 0, True, 2, 2),
            '<=': ('comp', 2, 0, True, 2, 2),
            '<': ('comp', 2, 0, True, 2, 2),
            '>=': ('comp', 2, 0, True, 2, 2),
            '>': ('comp', 2, 0, True, 2, 2)
        }.items()
    }
    # Global functions
    global_fns = {
        # name: (type, int_args, bool_args, bool_return, min_args, max_args)       .._args -1 = n-ary, min 2
        name: Function(name.__name__, name, *attrs)
        for name, attrs in {
            Abs: ('gfun', 1, 0, False, 1, 1),  # expr | (min 1, max 1, /)
            Minimum: ('gfun', -1, 0, None, 2, max_args),  # [...] | Can return a boolean but this is not known beforehand (min 2, max /)
            Maximum: ('gfun', -1, 0, None, 2, max_args),  # [...] | Can return a boolean but this is not known beforehand (min 2, max /)
            NValue: ('gfun', -1, 0, False, 2, max_args),  # [...] | (min 2, max /)
            Element: ('gfun', -1, 0, None, 2, max_args),  # [...], idx | Can return a boolean but this is not known beforehand (min 2, max /)
                                                        # Denk best enkel de array vullen en de idx gewoon tussen 0 en len-1 pakken
            Count: ('gfun', -1, 0, False, 2, max_args),  # [...], expr | (min 2, max /)
            Among: ('gfun', -1, 0, False, 2, max_args),  # [...], [...] | Second array can only have constants, no expressions (not even BoolVal()) (min 2, max /)
            NValueExcept: ('gfun', -1, 0, False, 2, max_args)  # [...], val | Second argument can only have constants, no expressions (not even BoolVal()) (min 2, max /)
        }.items()
    }
    # Global constraints
    global_cons = {
        # name: (type, int_args, bool_args, bool_return, min_args, max_args, multiple)       .._args -1 = n-ary, min 2
        name: Function(name.__name__, name, *attrs)
        for name, attrs in {
            AllDifferent: ('gcon', -1, 0, True, 2, max_args),  # [...] | (min 2, max /)
            AllDifferentExceptN: ('gcon', -1, 0, True, 2, max_args),  # [...], [...] | Second arg can also be a single non-list constant (min 2, max /)
            AllEqual: ('gcon', -1, 0, True, 2, max_args),  # [...] | (min 2, max /)
            AllEqualExceptN: ('gcon', -1, 0, True, 2, max_args),  # [...], [...] | Second arg can also be a single non-list constant (min 2, max /)
            Circuit: ('gcon', -1, 0, True, 2, max_args),  # [...] | Can only have ints, NO BOOLS! (min 2, max /)
            Inverse: ('gcon', -1, 0, True, 2, max_args),  # [...], [...] | Can only have ints, NO BOOLS! (min 2, max /)
            Table: ('gcon', -1, 0, True, 2, max_args),  # [...], [[...],[...],...] | First argument only variables, Second argument should have a multiple amnt of args as the first one (min 2, max /)
            NegativeTable: ('gcon', -1, 0, True, 2, max_args),  # [...], [[...],[...],...] | First argument only variables, Second argument should have a multiple amnt of args as the first one (min 2, max /)
            IfThenElse: ('gcon', 0, 3, True, 3, 3),  # arg1, arg2, arg3 (min 3, max 3)
            InDomain: ('gcon', -1, 0, True, 2, max_args),  # val, [...] | (min 2, max /)
            Xor: ('gcon', 0, -1, True, 1, max_args),  # [...] | (min 1, max /)
            # Cumulative: (-1, 0, True),  # st, dur, end, demand, cap (Ingewikkelde constraint)
            # Precedence: (?, ?, True),  # (Ingewikkelde constraint)
            NoOverlap: ('gcon', -1, 0, True, 3, max_args),  # [...], [...], [...] | Three lists all have same length (min 3, max /)
            GlobalCardinalityCount: ('gcon', -1, 0, True, 2, max_args),  # [...], [...], [...] | The first and last list have to be the same length and
                                                                        # they all have to be ints, NO BOOLS (min 2, max /)
            Increasing: ('gcon', -1, 0, True, 2, max_args),  # [...] (min 2, max /, /)
            Decreasing: ('gcon', -1, 0, True, 2, max_args),  # [...] (min 2, max /, /)
            IncreasingStrict: ('gcon', -1, 0, True, 2, max_args),  # [...] (min 2, max /, /)
            DecreasingStrict: ('gcon', -1, 0, True, 2, max_args),  # [...] (min 2, max /, /)
            LexLess: ('gcon', -1, 0, True, 2, max_args),  # [...], [...] | Lists have same length (min 2, max /), ONLY VARS
            LexLessEq: ('gcon', -1, 0, True, 2, max_args),  # [...], [...] | Lists have same length (min 2, max /), ONLY VARS
            LexChainLess: ('gcon', -1, 0, True, 2, max_args),  # [...][...] | Rows have same length (min 2, max /), ONLY VARS
            LexChainLessEq: ('gcon', -1, 0, True, 2, max_args),  # [...][...] | Rows have same length (min 2, max /), ONLY VARS
        }.items()
    }
    all_ops = ops | comps | global_fns | global_cons
    # print(f"ints_cnt={ints_cnt},bools_cnt={bools_cnt},has_bool_return={has_bool_return}")
    assert isinstance(ret_type, bool), f"Getting here means the return type should be a boolean. It is {ret_type}."
    after = {k: v for k, v in all_ops.items() if
             satisfies_args(v, ints_cnt, bools_cnt, constants_cnt, vars_cnt, ret_type)}
    if after:
        func = random.choice(list(after.values()))
    else:
        return None
    return generate_new_operator(func, ints, bools, constants, variables)


def find_all_occurrences(con: Expression, target_expr: Expression):
    """
    Recursively finds all occurrences of `target_expr` in the expression `con`.
    ~ Parameters:
        - `con`: constraint in which we search
        - `target_expr`: the expression we're searching the occurrences for
    ~ Returns:
        - `occurrences`: a list of paths (as tuples) to each occurrence.
    """
    occurrences = []
    # np.int32 didn't match with `is`
    if (isinstance(con, np.int32) and isinstance(target_expr, np.int32) and con == target_expr) or \
            con is target_expr:
        occurrences.append(())
    if hasattr(con, 'args') and not isinstance(con, NDVarArray) and con.name != 'boolval':
        for i, arg in enumerate(con.args):
            for path in find_all_occurrences(arg, target_expr):
                occurrences.append((i,) + path)  # Add index to the path
    elif isinstance(con, list) or isinstance(con, NDVarArray) or isinstance(con, tuple):
        for i, arg in enumerate(con):
            for path in find_all_occurrences(arg, target_expr):
                occurrences.append((i,) + path)
    return occurrences


def replace_at_path(con: Expression, path: tuple, new_expr: Expression):
    """
    Replace the Expression at the given `path` in the expression tree `con` with `new_expr`.

    ~ Parameters:
        - `con`: The constraint in which we will replace an expression
        - `path`: The path to the expression we will mutate (e.g. y has path (0, 1) in (x > y) -> p)
        - `new_expr`: The new expression which will be at the specified `path`
    ~ Returns:
        - `con`: The mutated constraint
    """
    if not path:  # Replace main expression
        return new_expr
    new_expr = copy.deepcopy(new_expr)  # Important to avoid infinite recursion!
    parent = con

    # Traverse the parents until we have the final parent
    for idx in path[:-1]:
        if hasattr(parent, 'args') and not isinstance(parent, NDVarArray) and parent.name != 'boolval':
            parent = parent.args[idx]
        elif isinstance(parent, list) or isinstance(parent, NDVarArray) or isinstance(parent, tuple):
            parent = parent[idx]

    # Change the arguments of the parent
    if hasattr(parent, 'args') and not isinstance(parent, NDVarArray) and parent.name != 'boolval':
        args = list(parent.args)
        args[path[-1]] = new_expr
        parent.update_args(args)
    elif isinstance(parent, list) or isinstance(parent, NDVarArray):
        parent[path[-1]] = new_expr
    elif isinstance(parent, tuple):
        parent = list(parent)
        parent[path[-1]] = new_expr
        parent = tuple(parent)
    return con


def expr_at_path(con: Expression, path: tuple, expr: Expression):
    """
    Helper function for checking whether the given expression is on the given path in the given constraint.
    Upon encountering `None` in a path, it will return True.
    """
    if not path and con is expr:
        return True
    # Traverse the parents until we have the final parent
    for idx in path:
        if idx is not None:
            if hasattr(con, 'args') and not isinstance(con, NDVarArray) and con.name != 'boolval':
                con = con.args[idx]
            elif isinstance(con, list) or isinstance(con, NDVarArray) or isinstance(con, tuple):
                con = con[idx]
        else:
            return len(find_all_occurrences(con, expr)) > 0
    return con is expr


def get_return_type(expr: Expression, con: Expression):
    """
    Function to get the return type of expressions that are allowed to replace `expr` in a given constraint `con`.
    There are four options:
        - boolean (any type of boolean including 'Expression's which are of type boolean (e.g. BoolVal(True), x == 5, p, ...))
        - int (any type of integer including 'Expression's which are of type int (e.g. 1, 1 + 2, x, ...))
        - constant (integers that are constants. No 'Expression's allowed. (e.g. 1, 2, ...; NOT: 1 + 2, x, ...))
        - variable (variables that aren't 'Expression's. (e.g. x, y, p, q; NOT: x == y, x > y, ...))
    ~ Parameters:
        - `expr`: the expression which we want to mutate
        - `con`: the constraint in which the expression is found
    ~ Returns:
        - `path`: the path at which the expression would be mutated
        - `ret_type`: the type that the expression is allowed to be mutated by, given either as a string or a boolean.
    """
    # Define functions of which the arguments are restricted to be constants and the remaining path length the argument would be in
    constant_restricted_functions = {Minimum: (1, (None,)),
                                     Maximum: (1, (None,)),
                                     Element: (2, (None,)),
                                     Among: (2, (1, None)),
                                     NValueExcept: (1, (1,)),
                                     Circuit: (1, (None,)),
                                     Inverse: (2, (None,)),
                                     GlobalCardinalityCount: (2, (None,)),
                                     Table: (3, (1, None)),
                                     NegativeTable: (3, (1, None)),
                                     # Count: (1, (1, None)),  # TODO: Is this still necessary?
                                     'pow': (1, (1, None)),
                                     'wsum': (2, (0, None))}
    variable_restricted_functions = {Table: (2, (0, None)),
                                     NegativeTable: (2, (0, None)),
                                     LexLess: (2, (None,)),
                                     LexLessEq: (2, (None,)),
                                     LexChainLess: (2, (None,)),
                                     LexChainLessEq: (2, (None,))}

    paths = find_all_occurrences(con, expr)
    path = random.choice(paths)
    path_len = len(path)
    for i, idx in enumerate(path):
        if type(con) in constant_restricted_functions:
            remaining_path_len, remaining_path = constant_restricted_functions[type(con)]
            if path_len - i == remaining_path_len and expr_at_path(con, remaining_path, expr):
                return path, 'constant'
        elif isinstance(con, Operator) and (con.name == 'wsum' or con.name == 'pow'):
            remaining_path_len, remaining_path = constant_restricted_functions[con.name]
            if path_len - i == remaining_path_len and expr_at_path(con, remaining_path, expr):
                return path, 'constant'
        if type(con) in variable_restricted_functions:
            remaining_path_len, remaining_path = variable_restricted_functions[type(con)]
            if path_len - i == remaining_path_len and expr_at_path(con, remaining_path, expr):
                return path, 'variable'
        if hasattr(con, 'args') and not isinstance(con, NDVarArray) and con.name != 'boolval':
            con = con.args[idx]
        elif isinstance(con, list) or isinstance(con, NDVarArray) or isinstance(con, tuple):
            con = con[idx]
    # We should only get here if the argument isn't in one of the functions above
    return path, is_boolexpr(expr)


def type_aware_expression_replacement(constraints: list):
    """
    Replaces a random expression of a random constraint from a list of given constraints. It replaces this expression
    by an operator with the same return type that takes as arguments the other expressions from all constraints.
    IMPORTANT: This can change satisfiability of the constraint! Only to be used with verifiers that allow this!
            This means it returns a list of ALL constraints and has to be handled accordingly in the 'generate_mutations'
            function to swap out the constraints instead of adding them.

    ~ Parameters:
        - `constraints`: a list of all the constraints to possibly be mutated
    ~ Return:
        - `final_cons`: a list of the same constraints where one constraint has a mutated expression
    """
    try:
        final_cons = copy.deepcopy(constraints)

        # 1. Neem een (random) expression van een (random) constraint en de return type
        rand_con = random.choice(final_cons)
        all_con_exprs = get_all_exprs(rand_con)
        expr = random.choice(all_con_exprs)
        path, ret_type = get_return_type(expr, rand_con)  # Also gives us the taken path of the expression in the constraint
                                                        # (Might be more than one occurrence so we should take the right one)
        # 2. Tel het aantal resterende params van elk type
        all_exprs = get_all_exprs_mult(final_cons)

        # 3. Zoek een operator die <= aantal params nodig heeft met zelfde return type
        new_expr = get_operator(all_exprs, ret_type)

        # 4. Vervang expression (+ vervang constraint)
        if new_expr:
            new_con = replace_at_path(rand_con, path, new_expr=new_expr)

            # 5. Return the new constraints
            # final_cons.remove(rand_con) DOES NOT WORK because it uses == instead of 'is'
            index = None
            for i, constraint in enumerate(final_cons):
                if constraint is rand_con:
                    index = i
                    break
            if index is not None:
                del final_cons[index]
            final_cons.append(new_con)
        return final_cons
    except Exception as e:
        raise Exception(e)


def has_positive_parity(expr: Expression, con: Expression, curr_path: tuple) -> tuple | None:
    """
    Function to retrieve the parity of an expression `expr` in the given constraint `con`. This means it shows
    whether the constraint weakens or strengthens when the expression does.
    ~ Parameters:
        - `expr`: the expression that would be strengthened/weakened.
        - `con`: the constraint that would be strengthened/weakened.
    ~ Returns:
        - `pos_parity`: True if the constraint strengthens (weakens) upon the expression strengthening,
                        False if it doesn't,
                        None if it is unknown.
    """
    # Basecase 1: `expr` cannot be strengthened or weakened
    if hasattr(expr, 'name'):
        # NOTE: these are not necessarily the only expressions that can be strengthened/weakened.
        #  (some double work is being done in function `is_changeable` so todo?)
        changeable_ops = {'and', 'or', '->', 'xor', '==', '!=', '<=', '<', '>=', '>'}
        changeable_globals = {AllDifferent, AllDifferentExceptN, AllEqual, AllEqualExceptN,
                              Table, NegativeTable, IncreasingStrict, DecreasingStrict,
                              LexLess, LexChainLess, Increasing, Decreasing, LexLessEq,
                              LexChainLessEq, InDomain}
        if not (expr.name in changeable_ops or type(expr) in changeable_globals):
            return None
    else:
        return None

    # Basecase 2:
    if expr is con:
        return True, curr_path

    # Recursively check in the arguments and change result upon encountering "not" operators
    # TODO: extend with other operators. e.g. the left side of `->` also has negative parity
    if con.name == 'not':
        curr_path += 0,
        neg_res = has_positive_parity(expr, con.args[0], curr_path)
        return not neg_res, curr_path if neg_res is not None else None
    if con.name == 'and' or con.name == 'or':
        args = con.args
        subtrees = list(enumerate(args))
        random.shuffle(subtrees)
        for path, subtree in subtrees:
            if any(expr is e for e in get_all_exprs(subtree)):  # check if expr is in the subtree
                curr_path += path,
                return has_positive_parity(expr, subtree, curr_path)
        raise Exception(f"The given expression {expr} is not in any of the arguments: {args}.")

    # If the constraint is anything else, we don't know the parity
    return None


def strengthen_expr(expr: Expression, path: tuple, con: Expression) -> Expression:
    """
    Strengthen the given expression `expr` in the given constraint `con`.
    ~ Parameters:
        - `expr`: the expression that will be strengthened.
        - `con`: the constraint that will be strengthened/weakened.
    ~ Returns:
        - `con`: the constraint after the mutation.
    """
    # TODO: 'and' & 'or' strengthenable by adding/removing args + other functions too
    match expr.name:  # {'or', '->', '!=', '<=', '>='}
        case 'or':  # and, xor, !=, <, >
            args = expr.args
            if len(args) != 2:
                return con
            comps = ['!=', '<', '>']
            ops = ['and']
            others = ['xor']
            new_op = random.choice(comps + ops + others)
        case '->':  # and, ==, <
            comps = ['==', '<']
            ops = ['and']
            new_op = random.choice(comps + ops)
            args = expr.args
        case '!=':  # <, >
            comps = ['<', '>']
            new_op = random.choice(comps)
            args = expr.args
        case '<=':  # <, ==
            comps = ['<', '==']
            new_op = random.choice(comps)
            args = expr.args
        case '>=':  # >, ==
            comps = ['>', '==']
            new_op = random.choice(comps)
            args = expr.args

    match expr:
        case Increasing():
            expr.name = 'IncreasingStrict'
        case Decreasing():
            expr.name = 'DecreasingStrict'
        case LexLessEq():
            expr.name = 'LexLess'
        case LexChainLessEq():
            expr.name = 'LexChainLess'
        case NegativeTable():
            fst_args, snd_args = expr.args
            random_idx = random.randrange(len(fst_args))
            new_fst_args = fst_args[:random_idx] + fst_args[random_idx + 1:]
            new_snd_args = [arg[:random_idx] + arg[random_idx + 1:] for arg in snd_args]
            expr.update_args((new_fst_args, new_snd_args))
        case InDomain():
            fst_args, snd_args = expr.args
            random_idx = random.randrange(len(snd_args))
            new_snd_args = snd_args[:random_idx] + snd_args[random_idx + 1:]
            expr.update_args((fst_args, new_snd_args))

    if 'new_op' in locals():  # Rewrite this later
        if new_op in comps:
            expr = Comparison(new_op, *args)
        elif new_op in ops:
            expr = Operator(new_op, args)
        elif new_op == 'xor':
            expr = Xor(args)

    con = replace_at_path(con, path, expr)
    return con


def weaken_expr(expr: Expression, path: tuple, con: Expression) -> Expression:
    """
    Weaken the given expression `expr` in the given constraint `con`.
    ~ Parameters:
        - `expr`: the expression that will be weakened.
        - `con`: the constraint that will be strengthened/weakened.
    ~ Returns:
        - `con`: the constraint after the mutation.
    """
    # TODO: 'and' & 'or' weakenable by removing/adding args + other functions too
    match expr.name:  # {'and', 'xor', '==', '<', '>'}
        case 'and':  # or, ->, ==, <=, >=
            args = expr.args
            if len(args) != 2:
                return con
            comps = ['==', '<=', '>=']
            ops = ['or', '->']
            new_op = random.choice(comps + ops)
        case 'xor':  # or
            args = expr.args
            if len(args) != 2:
                return con
            new_op = 'or'
        case '==':  # <=, >=
            comps = ['<=', '>=']
            new_op = random.choice(comps)
            args = expr.args
        case '<':  # !=, <=
            comps = ['!=', '<=']
            new_op = random.choice(comps)
            args = expr.args
        case '>':  # != >=
            comps = ['!=', '>=']
            new_op = random.choice(comps)
            args = expr.args

    match expr:
        case IncreasingStrict():
            expr.name = 'Increasing'
        case DecreasingStrict():
            expr.name = 'Decreasing'
        case LexLess():
            expr.name = 'LexLessEq'
        case LexChainLess():
            expr.name = 'LexChainLessEq'
        case Table():
            fst_args, snd_args = expr.args
            random_idx = random.randrange(len(fst_args))
            new_fst_args = fst_args[:random_idx] + fst_args[random_idx + 1:]
            new_snd_args = [arg[:random_idx] + arg[random_idx + 1:] for arg in snd_args]
            expr.update_args((new_fst_args, new_snd_args))
        case AllDifferent() | AllEqual():
            old_args = expr.args
            random_idx = random.randrange(len(old_args))
            new_args = old_args[:random_idx] + old_args[random_idx + 1:]
            expr.update_args(new_args)
        case AllDifferentExceptN() | AllEqualExceptN():
            fst_args, snd_args = expr.args
            random_idx = random.randrange(len(fst_args))
            new_fst_args = fst_args[:random_idx] + fst_args[random_idx + 1:]
            expr.update_args((new_fst_args, snd_args))

    if 'new_op' in locals():  # Rewrite this later
        if new_op in comps:
            expr = Comparison(new_op, *args)
        elif new_op in ops:
            expr = Operator(new_op, args)
        elif new_op == 'xor':
            expr = Xor(args)

    con = replace_at_path(con, path, expr)
    return con


def is_changeable(strengthen: bool, expr: Expression, pos_parity: bool) -> bool:
    # Sets to be extended when more weakening and strengthening options get added
    if strengthen ^ pos_parity:  # weakening
        is_changeable_op = expr.name in {'and', 'xor', '==', '>', '<'}
        is_changeable_global = type(expr) in {AllDifferent, AllDifferentExceptN, AllEqual, AllEqualExceptN,
                                              Table, NegativeTable, IncreasingStrict, DecreasingStrict,
                                              LexLess, LexChainLess}
    else:  # strengthening
        is_changeable_op = expr.name in {'or', '->', '!=', '<=', '>='}
        is_changeable_global = type(expr) in {Increasing, Decreasing, LexLessEq, LexChainLessEq, NegativeTable, InDomain}
    return is_changeable_op or is_changeable_global


def strengthening_weakening_mutator(constraints: list, strengthen: bool = True) -> list | Exception:
    """
    Strengthens or weakens a (random?) constraint from a list of given constraints by replacing an operator of this constraint.
    IMPORTANT: This can change satisfiability of the constraint! Only to be used with verifiers that allow this!
            This means it returns a list of ALL constraints and has to be handled accordingly in the 'generate_mutations'
            function to swap out the constraints instead of adding them.

    ~ Parameters:
        - `constraints`: a list of all the constraints to possibly be mutated
        - `strengthen`: a boolean indicating whether the mutator should strengthen or weaken a constraint
    ~ Return:
        - `final_cons`: a list of the same constraints where one constraint has a mutated operator
    """
    # TODO: right now: checks for possible expressions to strengthen/weaken and THEN calculates whether it should be
    #  strengthened or weakened.
    #       should be: calculate parity while searching for possible expressions and dismiss them if they can't be
    #  strengthened or weakened based on that.
    try:
        final_cons = copy.deepcopy(constraints)

        # pick a random constraint and calculate whether they have a mutable expression until they do
        candidates = []
        for item in constraints:
            if not any(item is cand for cand in candidates):
                candidates.append(item)
        # candidates = list(set(constraints))  # does not work with NDVarArray
        random.shuffle(candidates)
        for con in candidates:
            exprs = []
            for e in get_all_exprs(con):
                parity = has_positive_parity(e, con, curr_path=tuple())
                if parity is not None and is_changeable(strengthen, e, parity[0]):
                    exprs.append((e, parity))
            if exprs:
                break
        else:  # In case there isn't any mutable (weakening/strengthening depending on `strengthen`) expression in any constraint
            return final_cons

        # Remove the constraint from the constraints
        final_cons.remove(con)

        # Choose an expression to change
        expr, (pos_parity, path) = random.choice(exprs)

        # Mutate this expression
        if strengthen ^ pos_parity:  # weaken if parity is different from `strengthen`
            con = weaken_expr(expr, path, con)
        else:
            con = strengthen_expr(expr, path, con)

        # Add the changed constraint back
        final_cons.append(con)
        return final_cons

    except Exception as e:
        raise Exception(e)


def change_domain_mutator(constraints: list, strengthen: bool):
    # TODO? something else for boolean variables?
    try:
        # Take random integer variable
        variables = [v for v in get_variables(constraints) if not is_boolexpr(v)]
        if variables:  # Don't change if no integer variables
            rand_var = random.choice(variables)

            lb = rand_var.lb
            ub = rand_var.ub
            if strengthen:
                rand_var.lb = random.randint(lb, max(lb, ub - 1))
                rand_var.ub = random.randint(min(ub, rand_var.lb + 1), ub)
            else:
                expansion_param = 2  # How much bigger should the domain possibly be
                avg = (ub + lb) / 2
                max_ub = int(avg + (ub - avg) * expansion_param)
                min_lb = int(avg + (lb - avg) * expansion_param)
                rand_var.lb = random.randint(min_lb, lb)
                rand_var.ub = random.randint(ub, max_ub)

        # Return the given constraints to be compatible with how the other non-metamorphic mutators are called
        return constraints

    except Exception as e:
        raise Exception(e)


class MetamorphicError(Exception):
    pass


'''
returns a list of aritmetic expressions (as lists of indexes to traverse the expression tree)
that occur in the input expression. 
One (random) candidate is taken from each level of the expression if there exists one '''


def pickaritmetic(con, log=[], candidates=[]):
    if hasattr(con, 'name'):
        if con.name == 'wsum':
            # wsum has lists as arguments so we need a separate case
            # wsum is the lowest possible level
            return candidates + [log]
        if con.name == "element":  # or con.name == "table" or con.name == "cumulative":
            # no good way to know if element will return bool or not so ignore it
            return candidates
    if hasattr(con, "args"):
        iargs = [(j, e) for j, e in enumerate(con.args)]
        random.shuffle(iargs)
        for j, arg in iargs:
            if is_boolexpr(arg):
                res = pickaritmetic(arg, log + [j])
                if res != []:
                    return res
            elif is_any_list(arg):
                return pickaritmetic((arg, log + [j], candidates))
            else:
                return pickaritmetic(arg, log + [j], candidates + [log + [j]])

    return candidates


'''
Adapted pickaritmetic that only picks from arithmetic comparisons
used for mutators that i.e. multiple both sides with a number
returns a list of aritmetic expressions (as lists of indexes to traverse the expression tree)
that occur in the input expression. 
One (random) candidate is taken from each level of the expression if there exists one '''


def pickaritmeticComparison(con, log=[], candidates=[]):
    if hasattr(con, 'name'):
        if con.name == 'wsum':
            # wsum has lists as arguments so we need a separate case
            # wsum is the lowest possible level
            return candidates
        if con.name == "element" or con.name == "table" or con.name == 'cumulative':
            # no good way to know if element will return bool or not so ignore it (lists and element always return false to isbool)
            return candidates
    if hasattr(con, "args"):
        iargs = [(j, e) for j, e in enumerate(con.args)]
        random.shuffle(iargs)
        for j, arg in iargs:
            if is_boolexpr(arg):
                res = pickaritmeticComparison(arg, log + [j], candidates)
                if res != []:
                    return res
            else:
                if isinstance(con, Comparison):
                    return pickaritmeticComparison(arg, log + [j], candidates + [log])
                else:
                    return pickaritmeticComparison(arg, log + [j], candidates)

    return candidates
