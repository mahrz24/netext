from itertools import chain, cycle


def assert_output_equal(expected_output, actual_output):
    if expected_output != actual_output:
        diff = ""
        for i, (expected_line, actual_line) in enumerate(zip(chain(iter(expected_output.split("\n")), cycle("")), actual_output.split("\n"))):
            if expected_line != actual_line:
                line_diff = ""
                actual_line = actual_line.ljust(len(expected_line))
                for j, (expected_char, actual_char) in enumerate(zip(chain(iter(expected_line), cycle(" ")), actual_line)):
                    if expected_char != actual_char:
                        if expected_char == " ":
                            line_diff += "+"
                        elif actual_char == " ":
                            line_diff += "-"
                        else:
                            line_diff += "!"
                    else:
                        line_diff += f"{actual_char}"

                diff += f"! {line_diff}\n"
            else :
                diff += f"> {expected_line}\n"
        raise AssertionError(f"Output is not matching!\nExpected output:\n{expected_output}\n\nActual output:\n{actual_output}\nDiff:\n{diff}")
