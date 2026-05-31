import { Project, type SourceFile, SyntaxKind } from "ts-morph";
import { readFileSync } from "fs";

// you could also do this by using .findReferences() on the assert function
// https://ts-morph.com/navigation/finding-references

// what may still need to be done: search imports for local function imports (e.g. import { abc } from "./abc")
// and then inside the body of pbts, search for calls to these local functions.
// For called functions, add the source code.

export function loadFile(path: string) {
	const code = readFileSync(path, "utf-8");

	const project = new Project();
	const sourceFile = project.createSourceFile(path, code, {
		overwrite: true,
	});
	// Step 1: Find all assert identifiers from "fast-check"
	const assertNames = new Set<string>();
	let localFunctions: Record<
		string,
		{
			called: boolean;
			searchName: string;
			importPath: string;
			sourceCode?: string;
		}
	> = {};

	function getDepCanidatesByImport() {
		for (const importDecl of sourceFile.getImportDeclarations()) {
			// We search import declarations for possible assert names, they could be one of:
			// import { assert } from "fast-check";
			// import { assert as newName } from "fast-check";
			// import fc from "fast-check" // find fc.assert
			if (importDecl.getModuleSpecifierValue() === "fast-check") {
				for (const namedImport of importDecl.getNamedImports()) {
					if (namedImport.getName() === "assert") {
						assertNames.add(namedImport.getAliasNode()?.getText() || "assert");
					}
				}

				const defaultImport = importDecl.getDefaultImport();
				if (defaultImport) {
					assertNames.add(`${defaultImport.getText()}.assert`);
				}

				// Handle import * as fc from "fast-check"
				const namespaceImport = importDecl.getNamespaceImport();
				if (namespaceImport) {
					assertNames.add(`${namespaceImport.getText()}.assert`);
				}
			}

			// We also search for local functions that could be called in the tests
			if (importDecl.getModuleSpecifierValue().startsWith(".")) {
				for (const namedImport of importDecl.getNamedImports()) {
					localFunctions[
						namedImport.getAliasNode()?.getText() || namedImport.getName()
					] = {
						called: false,
						searchName: namedImport.getName(),
						importPath: importDecl.getModuleSpecifierValue(),
					};
				}

				const defaultImport = importDecl.getDefaultImport();
				if (defaultImport) {
					localFunctions[defaultImport.getText()] = {
						called: false,
						searchName: "default",
						importPath: importDecl.getModuleSpecifierValue(),
					};
				}
			}
		}
	}
	getDepCanidatesByImport();

	function addFileLocalFunctions(source: SourceFile) {
		// Find top-level function declarations and add them to localFunctions
		for (const funcDecl of source.getFunctions()) {
			const funcName = funcDecl.getName();
			if (funcName) {
				localFunctions[funcName] = {
					called: false,
					searchName: funcName,
					importPath: "local", // Indicates it's defined in the same file
					sourceCode: funcDecl.getText(),
				};
			}
		}

		// Also find function variables at the top level (const myFunc = () => {})
		for (const varDecl of source.getVariableDeclarations()) {
			if (
				varDecl.getInitializer()?.getKind() === SyntaxKind.ArrowFunction ||
				varDecl.getInitializer()?.getKind() === SyntaxKind.FunctionExpression
			) {
				const funcName = varDecl.getName();
				localFunctions[funcName] = {
					called: false,
					searchName: funcName,
					importPath: "local",
					sourceCode: varDecl.getVariableStatement()?.getText(),
				};
			}
		}
	}
	addFileLocalFunctions(sourceFile);

	// Step 2: Find call expressions matching assert names
	const tests = sourceFile
		// a call expression is a function call, e.g. abc(...)
		.getDescendantsOfKind(SyntaxKind.CallExpression)
		// filter calls to assert functions
		.filter((call) => {
			const expr = call.getExpression().getText();
			return assertNames.has(expr);
		})
		.flatMap((call) => {
			// currently, we have a handle on fc.assert, but we want the entire test.
			// first find the arrow function (e.g. test("abc", () => { ... }))
			//                                                 ^^^^^^^^^^^^^
			const body = call.getFirstAncestorByKind(SyntaxKind.ArrowFunction);
			// then get the wrapper function, the full test(...)
			let p = body?.getParent();
			if (!p) {
				return [];
			}

			// Check for calls to imported local functions within this test
			let functionsCalledInTest = new Set<string>();
			body
				?.getDescendantsOfKind(SyntaxKind.CallExpression)
				.forEach((callExpr) => {
					const exprText = callExpr.getExpression().getText();
					if (localFunctions[exprText]) {
						localFunctions[exprText].called = true;
						functionsCalledInTest.add(exprText);
					}
				});

			return [
				{
					test: p,
					functionsCalledInTest: Array.from(functionsCalledInTest),
				},
			];
		})
		.filter(Boolean);

	// Step 3: Find all calls to local functions
	for (const test of tests) {
		test.test
			.getDescendantsOfKind(SyntaxKind.CallExpression)
			.forEach((call) => {
				const expr = call.getExpression().getText();
				if (localFunctions[expr]) {
					localFunctions[expr].called = true;
				}
			});
	}

	localFunctions = Object.fromEntries(
		Object.entries(localFunctions).filter((f) => f[1].called),
	);

	// Step 4: Load source code for imported local functions
	const alreadyLoadedFiles = new Map<string, SourceFile>();

	for (const [name, func] of Object.entries(localFunctions)) {
		if (func.importPath === "local") {
			continue;
		}

		let importPath = func.importPath;

		if (!importPath.match(/\.(ts|js|tsx|jsx)$/)) {
			const possibleExtensions = [".ts", ".js", ".tsx", ".jsx"];
			let fileFound = false;

			for (const ext of possibleExtensions) {
				const pathWithExt = `${importPath}${ext}`;
				try {
					if (!alreadyLoadedFiles.has(pathWithExt)) {
						alreadyLoadedFiles.set(
							pathWithExt,
							project.addSourceFileAtPath(pathWithExt),
						);
					}
					importPath = pathWithExt;
					fileFound = true;
					break;
				} catch (error) {
					// Continue to next extension
				}
			}

			if (!fileFound) {
				console.warn(
					`Could not find file for ${importPath} with any supported extension`,
				);
				continue;
			}
		} else {
			// Already has extension
			if (!alreadyLoadedFiles.has(importPath)) {
				try {
					alreadyLoadedFiles.set(
						importPath,
						project.addSourceFileAtPath(importPath),
					);
				} catch (error) {
					console.warn(`Could not load file ${importPath}: ${error}`);
					continue;
				}
			}
		}

		const importedSourceFile = alreadyLoadedFiles.get(importPath)!;

		if (func.searchName === "default") {
			const defaultExport = importedSourceFile
				.getDefaultExportSymbol()
				?.getDeclarations()[0];
			if (defaultExport) {
				func.sourceCode = defaultExport.getText();
			}
		} else {
			// Handle named exports
			const exportedDeclarations = importedSourceFile.getExportedDeclarations();
			const declarations = exportedDeclarations.get(func.searchName);

			if (declarations && declarations.length > 0) {
				func.sourceCode = declarations[0].getText();

				// Crappy replacement attempt
				if (name !== func.searchName) {
					func.sourceCode = func.sourceCode
						.replace(
							new RegExp(`function\\s+${func.searchName}\\b`),
							`function ${name}`,
						)
						.replace(
							new RegExp(`const\\s+${func.searchName}\\s+=`),
							`const ${name} =`,
						);
				}
			}
		}
	}
	return {
		tests: tests.map((test) => ({
			test: test.test.getText(),
			testName:
				test.test.getFirstChildByKind(SyntaxKind.StringLiteral)?.getText() ||
				"unknown",
			functionsCalledInTest: test.functionsCalledInTest,
		})),
		localFunctions,
	};
}

//console.log(loadFile("./test/demo3.ts"));
