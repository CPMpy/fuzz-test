import copy
import random

import cpmpy
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
                 max_args: int = None,
                 multiple: int = 1):
        """
        type        = string that describes the type of function it is
        int_args    = the amount of args of type int it requires
        bool_args   = the amount of args of type bool it requires
        bool_return = a boolean representing whether it returns a boolean (False means int return type, None means it can be either)
        min_args    = the minimum amount of args the function takes
        max_args    = the maximum amount of args the function takes
        multiple    = the arguments have to be a multiple of this int
        """
        self.name = name
        self.func = func
        self.type = type_
        self.int_args = int_args
        self.bool_args = bool_args
        self.bool_return = bool_return
        self.min_args = min_args
        self.max_args = max_args
        self.multiple = multiple

    def __repr__(self):
        return (f"Operation({self.name}, {self.type}, {self.int_args}, {self.bool_args}, "
                f"{self.bool_return}, min_args={self.min_args}, max_args={self.max_args}, multiple={self.multiple})")


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


def type_aware_operator_replacement(constraints):
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
        - Int,  Int     -> Int  :  sum sub mul div mod pow
        - [Int, ...]    -> Int  :  sum
        - [Int]         -> Int  :  -
        - [Int, ...] [Int, ...] (arrays of same len) -> Int  :  wsum
    """
    try:
        final_cons = copy.deepcopy(constraints)
        cons_set = set(constraints)
        # pick a random constraint and calculate their mutable expressions until there is at least 1
        candidates = list(cons_set)  # or final_cons
        random.shuffle(candidates)
        for con in candidates:
            exprs = get_all_mutable_op_exprs(con)
            if exprs:
                break
        else:
            return final_cons

        # remove the constraint from the constraints
        final_cons.remove(con)

        # Choose an expression to change
        expr = random.choice(exprs)

        mutate_op_expression(expr, con)

        # add the changed constraint back
        final_cons.append(con)
        return final_cons

    except Exception as e:
        return Exception(e)


def mutate_op_expression(expr, con):
    """
    Mutates the constraint containing the expression by mutating said expression.
    Only to be called when the expression is known to be in the constraint.

    ~ Parameters:
        - expr: the expression that will be mutated
        - con: the constraint containing the expression
    ~ No return. Mutates the constraint!
    """
    # types that can be converted into each-other
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
        expr.name = new_operator
        return

    # recursively search in arguments
    if hasattr(con, "args"):
        for arg in con.args:
            mutate_op_expression(expr, arg)
            return


def get_all_mutable_op_exprs(con):
    """
    Returns a list of all expressions inside the given constraint of which the
    operator can be mutated into another one. This can be extended with other operators.

    ~ Paremeters:
        - con: a single constraint, possibly containing multiple expressions
    ~ Return:
        - mutable_exprs: all expressions in the constraint that can be mutated (safely)
    """
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


# Helper function to get all expressions WITH an operator in a given constraint
def get_all_op_exprs(con):
    if type(con) in {Comparison, Operator}:
        return sum((get_all_op_exprs(arg) for arg in con.args), []) + [con]  # All subexpressions + current expression
    else:
        return []


# Helper function to get all expressions WITHOUT an operator in a given constraint
def get_all_non_op_exprs(con):
    if hasattr(con, 'args') and type(con) != NDVarArray and con.name != 'boolval':
        return sum((get_all_non_op_exprs(arg) for arg in con.args), [])
    elif type(con) == list:
        if all([is_num(e) for e in con]):  # wsum constants
            return []
        else:
            return [e for e in con]
    else:
        return [con]


# Helper function to get all epxressions in a given constraint (Might be unnecessary but let's use this for now)
def get_all_exprs(con):
    return get_all_op_exprs(con)[::-1] + get_all_non_op_exprs(con)


def get_all_exprs_mult(cons):
    all_exprs = []
    for con in cons:
        all_exprs += get_all_exprs(con)
    return all_exprs


def satisfies_args(func: Function, ints: int, bools: int, values: int, vars: int, has_bool_return: bool):
    """
    returns whether the given function `func` can work with the given amount of integers `ints`
    and booleans `bools` and the given return type `has_bool_return`
    """
    match func.type:
        case 'op' | 'comp':
            match func.name:
                case 'wsum':
                    return values >= 1 and ints + bools >= func.min_args and has_bool_return == func.bool_return
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
                    return values >= func.min_args and not has_bool_return
                case 'Among' | 'NValueExcept':
                    return values >= 1 and ints >= func.min_args - 1 and not has_bool_return
        case 'gcon':
            match func.name:
                case 'Circuit' | 'Inverse' | 'GlobalCardinalityCount':
                    return values >= func.min_args and has_bool_return
                case 'IfThenElse' | 'Xor':
                    return bools >= func.min_args and has_bool_return
                case 'Table' | 'NegativeTable':
                    return vars >= 1 and ints + bools >= func.min_args - 1 and has_bool_return
                case 'LexLess' | 'LexLessEq' | 'LexChainLess' | 'LexChainLessEq':
                    return vars >= func.min_args and has_bool_return
                case _:
                    return ints + bools >= func.min_args and has_bool_return



def get_new_operator(func: Function, ints, bools, vals, variables):
    comb = ints + bools
    match func.type:
        case 'op' | 'comp':
            # Separate logic for wsum
            if func.name == 'wsum':  # (-1, 0, False, 2, max_args, 2)
                amnt_args = random.randint(func.min_args // 2, min(len(vals), func.max_args)//2)
                # First take constants
                constants = random.sample(vals, amnt_args)
                # Then the other expressions
                others = random.sample(comb, amnt_args)
                return Operator(func.name, [constants, others])

            # Logic for all other operators and comparisons is the same
            if func.int_args == -1:
                amnt_args = random.randint(func.min_args, min(len(comb), func.max_args))  # Take at least min_args and at most max_args arguments
                args = random.sample(comb, amnt_args)
            elif func.int_args > 0:
                args = random.sample(comb, func.int_args)
            if func.bool_args == -1:
                amnt_args = random.randint(func.min_args, min(len(bools), func.max_args))  # Take at least min_args and at most max_args arguments
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
                    amnt_args = random.randint(func.min_args, min(len(vals), func.max_args))
                    args = random.sample(vals, amnt_args),
                case 'Element':
                    amnt_args = random.randint(func.min_args, min(len(vals), func.max_args))
                    first_arg = random.sample(vals, amnt_args)
                    idx = random.randint(0, amnt_args - 1)
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
                    amnt_fst_arg = random.randint(func.min_args//2, min(len(comb), func.max_args)//2)
                    amnt_snd_arg = random.randint(func.min_args//2, min(len(vals), func.max_args)//2)
                    first_arg = random.sample(comb, amnt_fst_arg)
                    second_arg = random.sample(vals, amnt_snd_arg)
                    args = first_arg, second_arg
                case 'NValueExcept':
                    amnt_fst_arg = random.randint(func.min_args//2, min(len(comb), func.max_args)//2)
                    first_arg = random.sample(comb, amnt_fst_arg)
                    second_arg = random.choice(vals)
                    args = first_arg, second_arg
            return func.func(*args)
        case 'gcon':
            match func.name:
                case 'AllDifferent' | 'AllEqual' | 'Increasing' | 'Decreasing' | 'IncreasingStrict' | 'DecreasingStrict':
                    amnt_args = random.randint(func.min_args, min(len(comb), func.max_args))
                    args = random.sample(comb, amnt_args)
                case 'AllDifferentExceptN' | 'AllEqualExceptN':
                    amnt_fst_args = random.randint(func.min_args//2, min(len(comb), func.max_args)//2)
                    amnt_snd_args = random.randint(func.min_args//2, min(len(comb), func.max_args - amnt_fst_args))
                    args = random.sample(comb, amnt_fst_args), random.sample(comb, amnt_snd_args)
                case 'LexLess' | 'LexLessEq':
                    half_amnt_args = random.randint(func.min_args//2, min(len(variables), func.max_args)//2)
                    args = random.sample(variables, half_amnt_args), random.sample(variables, half_amnt_args)
                case 'LexChainLess' | 'LexChainLessEq':
                    amnt_args = random.randint(func.min_args, min(len(variables), func.max_args)//2)
                    all_args = random.sample(variables, amnt_args)
                    divisors = [i for i in range(1, amnt_args) if amnt_args % i == 0]
                    fst_dimension = random.choice(divisors)
                    snd_dimension = int(amnt_args / fst_dimension)
                    args = [all_args[i * fst_dimension:(i + 1) * fst_dimension] for i in range(snd_dimension)],
                case 'Circuit':
                    amnt_args = random.randint(func.min_args, min(len(vals), func.max_args))
                    args = random.sample(vals, amnt_args),
                case 'Inverse':
                    amnt_args = random.randint(func.min_args//2, min(len(vals), func.max_args)//2)
                    args = random.sample(range(1, amnt_args+1), amnt_args), random.sample(range(1, amnt_args+1), amnt_args)
                case 'IfThenElse':
                    amnt_args = random.randint(func.min_args, min(len(bools), func.max_args))
                    args = random.sample(bools, amnt_args)
                case 'Xor':
                    amnt_args = random.randint(func.min_args, min(len(bools), func.max_args))
                    args = random.sample(bools, amnt_args),
                case 'Table' | 'NegativeTable':
                    amnt_fst_arg = random.randint(1, min(len(variables), func.max_args//4))
                    amnt_snd_args = random.randint(1, min(len(comb), func.max_args-amnt_fst_arg) // amnt_fst_arg) * amnt_fst_arg
                    fst_args = random.sample(variables, amnt_fst_arg)
                    snd_args = random.sample(comb, amnt_snd_args)
                    snd_args_transformed = [snd_args[i * amnt_fst_arg:(i + 1) * amnt_fst_arg] for i in range(int(amnt_snd_args/amnt_fst_arg))]
                    args = fst_args, snd_args_transformed
                case 'InDomain':
                    amnt_args = random.randint(func.min_args, min(len(comb), func.max_args))
                    all_args = random.sample(comb, amnt_args)
                    args = all_args[0], all_args[1:]
                case 'NoOverlap':
                    amnt_args = random.randint(func.min_args, min(len(comb), func.max_args//3))
                    args = random.sample(comb, amnt_args), random.sample(comb, amnt_args), random.sample(comb, amnt_args)
                case 'GlobalCardinalityCount':
                    amnt_fst_args = random.randint(1, min(len(ints), func.max_args - 2))
                    amnt_snd_args = random.randint(1, min(len(ints), (func.max_args - amnt_fst_args)//2))
                    counts = [random.randint(0, amnt_fst_args) for _ in range(amnt_snd_args)]
                    args = random.sample(ints, amnt_fst_args), counts, random.sample(ints, amnt_snd_args)
                case _:
                    args = []
            return func.func(*args)

def get_operator(args, has_bool_return):
    """
    Returns a new expression that needs fewer arguments of each type than available in `args`.
    It has a boolean return type if `has_bool_return` is True, otherwise it has an int return type.
    """
    ints = [e for e in args if not (is_boolexpr(e) or type(e) == list)]
    bools = [e for e in args if is_boolexpr(e)]
    values = [e for e in args if not hasattr(e, 'value')]  # Is this the only way to extract constants only? (e.g. for wsum)
    variables = get_variables(args)
    ints_cnt = len(ints)
    bools_cnt = len(bools)
    vals_cnt = len(values)
    vars_cnt = len(variables)
    max_args = 12

    # Operators:
    ops = {
        # name: (type, int_args, bool_args, bool_return, min_args, max_args, multiple)       .._args -1 = n-ary, min 2
        name: Function(name, name, *attrs)
        for name, attrs in {
            'and': ('op', 0, -1, True, 2, max_args),
            'or': ('op', 0, -1, True, 2, max_args),
            '->': ('op', 0, 2, True, 2, 2),
            'not': ('op', 0, 1, True, 1, 1),
            'sum': ('op', -1, 0, False, 2, max_args),
            'wsum': ('op', -1, 0, False, 2, max_args, 2),
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
            Minimum: ('gfun', -1, 0, None, 2, max_args),  # [...] | Can return a boolean but this is not known beforehand (min 2, max /, /)
            Maximum: ('gfun', -1, 0, None, 2, max_args),  # [...] | Can return a boolean but this is not known beforehand (min 2, max /, /)
            NValue: ('gfun', -1, 0, False, 2, max_args),  # [...] | (min 2, max /, /)
            Element: ('gfun', -1, 0, None, 2, max_args),  # [...], idx | Can return a boolean but this is not known beforehand (min 2, max /, /)
                                                        # Denk best enkel de array vullen en de idx gewoon tussen 0 en len-1 pakken
            Count: ('gfun', -1, 0, False, 2, max_args),  # [...], expr | (min 2, max /, /)
            Among: ('gfun', -1, 0, False, 2, max_args),  # [...], [...] | Second array can only have values, no expressions (not even BoolVal()) (min 2, max /, /)
            NValueExcept: ('gfun', -1, 0, False, 2, max_args)  # [...], val | Second argument can only have values, no expressions (not even BoolVal()) (min 2, max /, /)
        }.items()
    }
    # Global constraints
    global_cons = {
        # name: (type, int_args, bool_args, bool_return, min_args, max_args, multiple)       .._args -1 = n-ary, min 2
        name: Function(name.__name__, name, *attrs)
        for name, attrs in {
            AllDifferent: ('gcon', -1, 0, True, 2, max_args),  # [...] | (min 2, max /, /)
            AllDifferentExceptN: ('gcon', -1, 0, True, 2, max_args),  # [...], [...] | Second arg can also be a single non-list value (min 2, max /, /)
            AllEqual: ('gcon', -1, 0, True, 2, max_args),  # [...] | (min 2, max /, /)
            AllEqualExceptN: ('gcon', -1, 0, True, 2, max_args),  # [...], [...] | Second arg can also be a single non-list value (min 2, max /, /)
            Circuit: ('gcon', -1, 0, True, 2, max_args),  # [...] | Can only have ints, NO BOOLS! (min 2, max /, /)
            Inverse: ('gcon', -1, 0, True, 2, max_args, 2),  # [...], [...] | Can only have ints, NO BOOLS! (min 2, max /, 2n)
            Table: ('gcon', -1, 0, True, 2, max_args),  # [...], [[...],[...],...] | First argument only variables, Second argument should have a multiple amnt of args as the first one (min 2, max /, n + mn?)
            NegativeTable: ('gcon', -1, 0, True, 2, max_args),  # [...], [[...],[...],...] | First argument only variables, Second argument should have a multiple amnt of args as the first one (min 2, max /, n + mn?)
            IfThenElse: ('gcon', 0, 3, True, 3, 3),  # arg1, arg2, arg3 (min 3, max 3, /)
            InDomain: ('gcon', -1, 0, True, 2, max_args),  # val, [...] | (min 2, max /, /)
            Xor: ('gcon', 0, -1, True, 1, max_args),  # [...] | (min 1, max /, /)
            # Cumulative: (-1, 0, True),  # st, dur, end, demand, cap (Ingewikkelde constraint)
            # Precedence: (?, ?, True),  # (Ingewikkelde constraint)
            NoOverlap: ('gcon', -1, 0, True, 3, max_args, 3),  # [...], [...], [...] | Three lists all have same length (min 3, max /, 3n)
            GlobalCardinalityCount: ('gcon', -1, 0, True, 2, max_args),  # [...], [...], [...] | The first and last list have to be the same length and
                                                                        # they all have to be ints, NO BOOLS (min 2, max /, /)
            Increasing: ('gcon', -1, 0, True, 2, max_args),  # [...] (min 2, max /, /)
            Decreasing: ('gcon', -1, 0, True, 2, max_args),  # [...] (min 2, max /, /)
            IncreasingStrict: ('gcon', -1, 0, True, 2, max_args),  # [...] (min 2, max /, /)
            DecreasingStrict: ('gcon', -1, 0, True, 2, max_args),  # [...] (min 2, max /, /)
            LexLess: ('gcon', -1, 0, True, 2, max_args, 2),  # [...], [...] | Lists have same length (min 2, max /, 2n), ONLY VARS
            LexLessEq: ('gcon', -1, 0, True, 2, max_args, 2),  # [...], [...] | Lists have same length (min 2, max /, 2n), ONLY VARS
            LexChainLess: ('gcon', -1, 0, True, 2, max_args),  # [...][...] | Rows have same length (min 2, max /, mn), ONLY VARS
            LexChainLessEq: ('gcon', -1, 0, True, 2, max_args),  # [...][...] | Rows have same length (min 2, max /, mn), ONLY VARS
        }.items()
    }
    all_ops = ops | comps | global_fns | global_cons
    # print(f"ints_cnt={ints_cnt},bools_cnt={bools_cnt},has_bool_return={has_bool_return}")
    after = {k: v for k, v in all_ops.items() if satisfies_args(v, ints_cnt, bools_cnt, vals_cnt, vars_cnt, has_bool_return)}
    if after:
        func = random.choice(list(after.values()))
    else:
        return None
    return get_new_operator(func, ints, bools, values, variables)

def find_all_occurrences(con, target_node):
    """
    Recursively finds all occurrences of `target_node` in the expression `con`.
    Returns a list of paths (as tuples) to each occurrence.
    """
    occurrences = []
    if con is target_node:
        occurrences.append(())  # Current node is the target
    if hasattr(con, 'args') and con.name != 'boolval':
        for i, arg in enumerate(con.args):
            for path in find_all_occurrences(arg, target_node):
                occurrences.append((i,) + path)  # Add index to the path
    elif type(con) == list:
        for i, arg in enumerate(con):
            for path in find_all_occurrences(arg, target_node):
                occurrences.append((i,) + path)
    return occurrences


def replace_at_path(con, path, new_expr):
    if not path:  # END OF PATH
        return new_expr
    if hasattr(con, 'args') and con.name != 'boolval':
        args = con.args
        args[path[0]] = replace_at_path(args[path[0]], path[1:], new_expr)
        if type(con) == Operator:
            return Operator(con.name, args)
        if type(con) == Comparison:
            return Comparison(con.name, args[0], args[1])
        else:  # global constraints
            return type(con)(*args)
    elif type(con) == list:
        return [new_expr if i == path[0] else e for i, e in enumerate(con)]
    else:
        return con


def mutate_con(con, old_expr, new_expr):
    paths = find_all_occurrences(con, old_expr)
    rand_path = random.choice(paths)
    return replace_at_path(con, rand_path, new_expr)


def type_aware_expression_replacement(constraints):
    """
    Replaces a random expression of a random constraint from a list of given constraints. It replaces this expression
    by an operator with the same return type that takes as arguments the other expressions from all constraints.
    IMPORTANT: This can change satisfiability of the constraint! Only to be used with verifiers that allow this!
            This means it returns a list of ALL constraints and has to be handled accordingly in the 'generate_mutations'
            function to swap out the constraints instead of adding them.

    ~ Parameters:
        - constraints: a list of all the constraints to possibly be mutated
    ~ Return:
        - final_cons: a list of the same constraints where one constraint has a mutated expression
    """
    final_cons = copy.deepcopy(constraints)
    # print(f"All constraints at the moment: {final_cons}")
    # 1. Neem een (random) expression van een (random) constraint en de return type
    rand_con = random.choice(final_cons)
    all_con_exprs = get_all_exprs(rand_con)
    expr = random.choice(all_con_exprs)
    has_bool_return = is_boolexpr(expr)
    # print(f"Changing constarint: {rand_con}")
    # print(f"Old expression: {expr}")
    # 2. Tel het aantal resterende params van elk type (van alle constraints of enkel in de constraint zelf?)
    all_exprs = get_all_exprs_mult(final_cons)
    # 3. Zoek een operator die <= aantal params nodig heeft met zelfde return type
    new_expr = get_operator(all_exprs, has_bool_return)
    # 4. Vervang expression (+ vervang constraint)
    # print(f"New expression: {new_expr}")
    if new_expr:
        new_con = mutate_con(rand_con, old_expr=expr, new_expr=new_expr)
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
