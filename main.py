import re
import os
from subprocess import Popen, PIPE
from pathlib import Path
import shutil
import string


def write_file(filename, text):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(text)


class Node:
    def __init__(self, start: str, content: [str], subnodes):
        self.start = start
        self.content = content
        self.subnodes = subnodes


class SwiftParser:
    def __init__(self, text: str):
        self.text = text

        lines = text.split('\n')

        index_of_class_end = lines.index('}')

        self.extensions = lines[index_of_class_end + 1:]
        lines = lines[:index_of_class_end + 1]

        self.root, _ = self.parse_node('root', lines)

    def parse_node(self, start, lines):
        content = []
        subnodes = []

        open_count = 0
        close_count = 0

        idx = 0
        while idx < len(lines):
            line = lines[idx]

            quick_funcs = [
                'override func spec(',
                'beforeEach',
                'describe(',
                'context(',
                'it(',
                'class ',
                'final class '
            ]
            quick_funcs = [
                line.strip().startswith(x)
                for x in quick_funcs
            ]
            is_start_of_node = '{' in line and '}' not in line and True in quick_funcs

            if is_start_of_node:
                n, n_length = self.parse_node(line, lines[idx + 1:])

                idx += n_length + 1
                subnodes.append(n)
            else:
                open_count += line.count('{')
                close_count += line.count('}')

                if '}' == line.strip() and open_count == close_count - 1:
                    return Node(start=start, content=content, subnodes=subnodes), idx
                else:
                    content.append(line)

            idx += 1

        return Node(start=start, content=content, subnodes=subnodes), idx


def strip_array(arr: [str]):
    return [x.strip() for x in arr]


class QuickParser:
    class TestCase:
        def __init__(self, naming: [str], content: [str], before_each: [str], vars: [str]):
            self.naming = naming
            self.content = content
            self.before_each = before_each
            self.vars = vars

    def __init__(self, text: str, root_node: Node, extensions: [str]):
        self.text = text
        self.extensions = extensions
        self.common_setup = []
        self.common_vars = []

        # self.imports = re.findall(r'import (\w+)', text, flags=re.MULTILINE)
        self.class_name = re.findall(r'class (\w+): QuickSpec \{', text, flags=re.MULTILINE)[0].replace('Spec', 'Tests')

        self.root_node = root_node

        self.test_cases: list[QuickParser.TestCase] = []

        self.process_node(root_node)

        self.strip_all()
        self.extract_commons()
        self.cleanup_test_cases()

        self.testable_name = None
        for var in self.common_vars:
            match = re.search(r'var (\w+): (\w+)', var)
            if match:
                var_name = match.group(1)
                var_type = match.group(2)

                if var_type in self.class_name:
                    self.testable_name = var_name

    def strip_all(self):
        for result in self.test_cases:
            result.naming = strip_array(result.naming)
            result.content = strip_array(result.content)
            result.before_each = strip_array(result.before_each)
            result.vars = strip_array(result.vars)

    def process_node(self, node: Node,
                     context_content=[],
                     context_naming=[],
                     context_before_each=[],
                     context_vars=[],
                     level=0):
        my_naming = context_naming + [node.start]
        my_content = context_content + node.content
        my_before_each = list(context_before_each)
        my_vars = list(context_vars)

        for line in node.content:
            if line.strip().startswith('var '):
                my_vars.append(line)

        for n in node.subnodes:
            if 'beforeEach {' == n.start.strip():
                if level <= 3:
                    my_before_each += n.content
                else:
                    my_content += n.content

            self.process_node(n, my_content, my_naming, my_before_each, my_vars, level + 1)

        it_name = re.findall(r'it\("(.+)"\)', node.start)
        if len(it_name) == 1:
            result = QuickParser.TestCase(naming=my_naming,
                                          content=my_content,
                                          before_each=my_before_each,
                                          vars=my_vars)
            self.test_cases.append(result)

    def extract_commons(self):
        def extract(array_key: str):
            res = {}
            for r in self.test_cases:
                for val in r.__dict__[array_key]:
                    if val not in res:
                        res[val] = 1
                    else:
                        res[val] += 1

            common = [x for x in res.keys() if res[x] == len(self.test_cases)]
            return common

        self.common_setup = extract("before_each")
        self.common_vars = extract("vars")

    def cleanup_test_cases(self):
        for test in self.test_cases:
            test.before_each = [x for x in test.before_each
                                if x not in self.common_setup]
            test.content = [x for x in test.content
                            if x not in self.root_node.content
                            and not x.startswith("//swiftlint")
                            and not x.startswith("// swiftlint")
                            and x not in self.common_vars]


class XCTestGenerator:
    def __init__(self, parser: QuickParser):
        self.parser = parser

    def generate_setup(self):
        common_before_each = self.parser.common_setup
        common_before_each_str = '\n'.join(common_before_each)

        return f'''override func setUp() {{
            super.setUp()
            {common_before_each_str}
        }}\n\n'''

    def generate_teardown(self):
        tear_downs = [
            x.split('=')[0] + '= nil'
            for x in self.parser.common_setup if '=' in x
        ]
        tear_downs.reverse()
        tear_downs_str = '\n'.join(tear_downs)

        return f'''override func tearDown() {{
            {tear_downs_str}
            super.tearDown()
        }}\n\n'''

    def generate_test_case(self, test: QuickParser.TestCase, used_test_names: set):
        def convert_expectations(line: str):
            if not line.endswith('in') and line.count('{') == line.count('}'):
                line = re.sub(r'expect\((.+?)\) == (.+?)$', r'XCTAssertEqual(\g<1>, \g<2>)', line)
            line = re.sub(r'expect\((.+?)\) === (.+?)$', r'XCTAssertTrue(\g<1> === \g<2>)', line)
            line = re.sub(r'expect\((.+?)\).to\(beNil\(\)\)', r'XCTAssertNil(\g<1>)', line)
            line = re.sub(r'expect\((.+?)\).(?:notTo|toNot)\(beNil\(\)\)', r'XCTAssertNotNil(\g<1>)', line)
            line = re.sub(r'expect\((.+?)\).to\(beAKindOf\((.+?)\.self\)\)', r'XCTAssertTrue(\g<1> is \g<2>)', line)

            line = re.sub(r'expect\(expression:\s*(.+?)\s*\)\.to\(throwError\((.+)\)\)',
                          r'customAssertThrowsError(expression: \g<1>, expectedError: \g<2>)', line)

            line = re.sub(r'expect\(expression:\s*(.+?)\s*\)\.to\(throwError\(\)\)',
                          r'customAssertThrowsError(expression: \g<1>)', line)

            line = re.sub(r'expect\(expression:\s*(.+?)\s*\)\.(?:toNot|notTo)\(throwError\(\)\)',
                          r'customAssertNoThrow(expression: \g<1>)', line)
            return line

        def join_declarations_and_assignments(lines):
            class VAR:
                def __init__(self, name, type, declaration_idx):
                    self.name = name
                    self.type = type.replace('!', '').replace('?', '')
                    self.value = None
                    self.declaration_idx = declaration_idx
                    self.assignment_idx = None
                    self.should_be_var = False

                @property
                def joined(self):
                    var_type = 'var' if self.should_be_var else 'let'
                    return f'{var_type} {self.name}: {self.type} = {self.value}'

            vars = {}

            # find declarations
            for idx, line in enumerate(lines):
                match = re.search(r'var (\w+): (\S+)', line)
                if match and ('=' not in line or '= []' in line or '= ""' in line):
                    vars[match.group(1)] = VAR(name=match.group(1), type=match.group(2), declaration_idx=idx)

            # find assignments
            for idx, line in enumerate(lines):
                match = re.search(r'^(\w+) = (.+)$', line)
                if match and match.group(1) in vars:
                    name = match.group(1)

                    if vars[name].value is None:
                        vars[name].value = match.group(2)
                        vars[name].assignment_idx = idx
                    else:
                        vars[name].should_be_var = True

            # result
            for _, var in vars.items():
                lines[var.declaration_idx] = ''
                if var.value:
                    lines[var.assignment_idx] = var.joined

            lines = [x for x in lines if x != '']

            return lines

        def fix_xctfail(lines):
            return [
                x.replace('fail(', 'XCTFail(')
                for x in lines
            ]

        body_lines = test.before_each + test.content
        body_lines = join_declarations_and_assignments(body_lines)
        body_lines = fix_xctfail(body_lines)
        body_lines = [convert_expectations(x) for x in body_lines]

        def generate_test_name():
            naming = []
            for x in test.naming[4:]:
                match = re.search(r'describe\("(.*)"\)', x)
                if match:
                    naming.append(match.group(1))
                match = re.search(r'context\("(.*)"\)', x)
                if match:
                    naming.append(match.group(1))
                match = re.search(r'it\("(.*)"\)', x)
                if match:
                    naming.append('it ' + match.group(1))

            naming_raw = ' '.join(naming).title()

            allowed_characters = string.digits + string.ascii_letters
            test_name = ''.join([x for x in naming_raw if x in allowed_characters])
            func_name = 'test' + test_name

            if len(func_name) >= 100:
                naming_raw = ' _ '.join(naming)
                naming_raw = naming_raw.title()
                allowed_characters += '_'
                test_name = ''.join([x for x in naming_raw if x in allowed_characters])
                func_name = 'test' + test_name

            duplicate_detected = False
            while func_name in used_test_names:
                duplicate_detected = True
                match = re.search(r'^\D+(\d+)$', func_name)
                if match:
                    number = int(match.group(1)) + 1
                    func_name = func_name.split('#')[0] + '#' + str(number)
                else:
                    func_name += '#1'

            used_test_names.add(func_name)
            func_name = func_name.replace('#', '_')

            if duplicate_detected:
                print("Duplicate func name fixed: " + func_name)

            return func_name, naming_raw

        def insert_arrange_act_assert(lines, testable_name):
            lines = [x for x in lines if x != '']

            last_testable_call_idx = None
            for idx, line in enumerate(lines):
                if re.search(rf'\W?{testable_name}\W', line) and 'Assert' not in line:
                    last_testable_call_idx = idx

            if last_testable_call_idx is not None:
                lines.insert(last_testable_call_idx, '\n// act')

                line_before_assert = lines[last_testable_call_idx + 1]
                assert_comment = '// assert' \
                    if line_before_assert.count('{') > line_before_assert.count('}') \
                    else '\n// assert'

                lines.insert(last_testable_call_idx + 2, assert_comment)
            else:
                first_assert_idx = next((i for i, v in enumerate(lines) if 'Assert' in v), None)
                if first_assert_idx:
                    lines.insert(first_assert_idx, '\n// assert')

            if lines[0] != '\n// act':
                lines.insert(0, '// arrange')

            return '\n'.join(lines)

        func_name, _ = generate_test_name()
        test_body = insert_arrange_act_assert(body_lines, self.parser.testable_name)

        result = f'''func {func_name}() {{
            {test_body}
        }}'''

        return result

    def generate_test_cases(self):
        used_test_names = set()
        cases = [self.generate_test_case(x, used_test_names) for x in self.parser.test_cases]
        return '\n\n'.join(cases)

    def generate(self):
        xctest = self.parser.text.split('class')[0] \
            .replace("import Quick\n", "") \
            .replace("import Nimble", "import XCTest")

        xctest += f'class {self.parser.class_name}: XCTestCase {{\n\n'

        xctest += '\n'.join(self.parser.common_vars) + '\n\n'
        xctest += self.generate_setup()
        xctest += self.generate_teardown()
        xctest += self.generate_test_cases()

        xctest += '\n}'

        if self.parser.extensions:
            xctest += '\n\n' + '\n'.join(self.parser.extensions)

        return xctest


def convert_quick(filename, out_dir):
    with open(filename, 'r', encoding='utf-8') as file:
        text = file.read()

    swift_parser = SwiftParser(text)
    parser = QuickParser(text, swift_parser.root, swift_parser.extensions)

    test = XCTestGenerator(parser).generate()

    out_file = filename.replace('unwrapped/', 'out/')
    write_file(out_file, test)

    run_swiftformat(out_file)


def run_swiftformat(swift_file):
    process = Popen(['swiftformat', swift_file], stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()

    stdout = stdout.decode('utf-8')
    stderr = stderr.decode('utf-8')

    print(stdout + stderr)


def remove_line_wraps(filename, out_file):
    with open(filename, 'r', encoding='utf-8') as file:
        text = file.read()

    index = text.index(': QuickSpec {')
    first = text[:index]
    second = text[index:]

    second = re.sub(r'([\.,\[\(=:])\s*\n\s*', r'\g<1>', second, flags=re.MULTILINE)

    second = re.sub(r'\s*\n\s*([\.,\]\)=])', r'\g<1>', second, flags=re.MULTILINE)

    write_file(out_file, first + second)


def unwrap_all_files():
    try:
        shutil.rmtree('unwrapped')
    except FileNotFoundError:
        pass

    for path in Path('src').rglob('*.swift'):
        with open(str(path), 'r', encoding='utf-8') as file:
            text = file.read()
            if 'QuickSpec' not in text:
                print(f"Skipped file without QuickSpec: {path}")
                continue

        remove_line_wraps(path, str(path).replace('src', 'unwrapped'))


def convert_all_files():
    try:
        shutil.rmtree('out')
    except FileNotFoundError:
        pass

    for path in Path('unwrapped').rglob('*.swift'):
        print(f'==== Processing {path} ====')
        convert_quick(str(path), out_dir='out')


unwrap_all_files()
convert_all_files()

# convert_quick(str('unwrapped/example.swift'), out_dir='out')

print("!!! Check file `CustomThrowingAssertFunctions.swift` for definitions of"
      "\n\t`customAssertThrowsError`\n\t`customAssertNoThrow`")
