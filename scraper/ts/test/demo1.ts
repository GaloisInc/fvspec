import fc from "fast-check";
import { assert as wierdName } from "fast-check";
import { describe, test, expect } from "bun:test";
import { a as b, sortStringsAscending } from "../demo2.ts";

const thisIsNotRelevant = "";

const a = () => {};
const c = () => {};

describe("My first property-based test", () => {
  test("should sort numeric elements from the smallest to the largest one", () => {
    wierdName(
      fc.property(fc.array(fc.integer()), (data) => {
        const sortedData = sortNumbersAscending(data);
        for (let i = 1; i < data.length; ++i) {
          expect(sortedData[i - 1]).toBeLessThanOrEqual(sortedData[i]);
        }
        a();
        b();
      })
    );
  });

  test("should sort string elements alphabetically", () => {
    fc.assert(
      fc.property(fc.array(fc.string()), (data) => {
        const sortedData = sortStringsAscending(data);
        for (let i = 1; i < data.length; ++i) {
          expect(sortedData[i - 1]).toBeLessThanOrEqual(sortedData[i]);
        }
      })
    );
  });
});
