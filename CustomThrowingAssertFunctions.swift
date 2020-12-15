/// Замена `XCTAssertThrowsError`, которая не работает.
func customAssertThrowsError<R>(
	expression: () throws -> R,
	file: StaticString = #filePath,
	line: UInt = #line
) {
	do {
		_ = try expression()
		XCTFail("Выражение должно выбросить ошибку!", file: file, line: line)
	} catch { }
}

/// Замена `XCTAssertThrowsError`, которая не работает.
func customAssertThrowsError<E: Error & Equatable, R>(
	expression: () throws -> R,
	expectedError: E,
	file: StaticString = #filePath,
	line: UInt = #line
) {
	do {
		_ = try expression()
		XCTFail("Выражение должно выбросить ошибку!", file: file, line: line)
	} catch {
		XCTAssertEqual(error as? E, expectedError, file: file, line: line)
	}
}

/// Замена `XCTAssertNoThrow`, которая не работает.
func customAssertNoThrow<R>(
	expression: () throws -> R,
	file: StaticString = #filePath,
	line: UInt = #line
) {
	do {
		_ = try expression()
	} catch {
		XCTFail("Выражение не должно выбросить ошибку!", file: file, line: line)
	}
}