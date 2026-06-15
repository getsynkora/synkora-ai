export type CompareMode = 'exact' | 'float' | 'sort' | 'sortNested'

export type CodingTestCase = {
  name: string
  input: unknown[]
  expected: unknown
  compare?: CompareMode
}

export type CodingProblemDetail = {
  slug: string
  title: string
  topic: string
  difficulty: string
  source: string
  statement: string
  signature: string
  functionName: string
  starterCode: string
  examples: { input: string; output: string; note?: string }[]
  constraints: string[]
  tests: CodingTestCase[]
  hints: string[]
  judgeReady: boolean
}

type ProblemTuple = readonly [string, string, string, string]

const slugify = (title: string) => title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

const makeStarter = (functionName: string, args: string, note = 'Implement your solution here.') => `from typing import List

def ${functionName}(${args}):
    """${note}"""
    pass
`

const definedProblems: Record<string, Omit<CodingProblemDetail, 'slug' | 'source' | 'judgeReady'>> = {
  'merge-strings-alternately': {
    title: 'Merge Strings Alternately',
    topic: 'Array / String',
    difficulty: 'Easy',
    statement: 'Build a new string by taking one character from each input string in alternating order. Append the remaining suffix when one string is exhausted.',
    signature: 'def mergeAlternately(word1: str, word2: str) -> str',
    functionName: 'mergeAlternately',
    starterCode: makeStarter('mergeAlternately', 'word1: str, word2: str', 'Return the merged alternating string.'),
    examples: [
      { input: 'word1 = "abc", word2 = "pqr"', output: '"apbqcr"' },
      { input: 'word1 = "ab", word2 = "pqrs"', output: '"apbqrs"' },
    ],
    constraints: ['Use each character exactly once.', 'Handle different string lengths.'],
    tests: [
      { name: 'same length', input: ['abc', 'pqr'], expected: 'apbqcr' },
      { name: 'second longer', input: ['ab', 'pqrs'], expected: 'apbqrs' },
      { name: 'first longer', input: ['abcd', 'pq'], expected: 'apbqcd' },
    ],
    hints: ['Two indices are enough.', 'A zip-style loop plus suffix handling is acceptable.'],
  },
  'greatest-common-divisor-of-strings': {
    title: 'Greatest Common Divisor of Strings',
    topic: 'Array / String',
    difficulty: 'Easy',
    statement: 'Return the largest base string that can be repeated to construct both input strings. If no such base exists, return an empty string.',
    signature: 'def gcdOfStrings(str1: str, str2: str) -> str',
    functionName: 'gcdOfStrings',
    starterCode: makeStarter('gcdOfStrings', 'str1: str, str2: str', 'Return the largest repeated base string.'),
    examples: [
      { input: 'str1 = "ABCABC", str2 = "ABC"', output: '"ABC"' },
      { input: 'str1 = "LEET", str2 = "CODE"', output: '""' },
    ],
    constraints: ['The base must tile both strings exactly.', 'Return the longest valid base.'],
    tests: [
      { name: 'shared base', input: ['ABCABC', 'ABC'], expected: 'ABC' },
      { name: 'larger repeated base', input: ['ABABAB', 'ABAB'], expected: 'AB' },
      { name: 'no common base', input: ['LEET', 'CODE'], expected: '' },
    ],
    hints: ['If str1 + str2 differs from str2 + str1, no base exists.', 'The base length is the gcd of the two lengths.'],
  },
  'kids-with-the-greatest-number-of-candies': {
    title: 'Kids With the Greatest Number of Candies',
    topic: 'Array / String',
    difficulty: 'Easy',
    statement: 'For each child, decide whether giving them all extra candies would make their count at least as large as the current maximum.',
    signature: 'def kidsWithCandies(candies: List[int], extraCandies: int) -> List[bool]',
    functionName: 'kidsWithCandies',
    starterCode: makeStarter('kidsWithCandies', 'candies: List[int], extraCandies: int', 'Return one boolean per child.'),
    examples: [
      { input: 'candies = [2,3,5,1,3], extraCandies = 3', output: '[True, True, True, False, True]' },
    ],
    constraints: ['Do not mutate the input list.', 'Compare against the original maximum.'],
    tests: [
      { name: 'mixed results', input: [[2, 3, 5, 1, 3], 3], expected: [true, true, true, false, true] },
      { name: 'all become max', input: [[4, 2, 1, 1, 2], 1], expected: [true, false, false, false, false] },
      { name: 'already tied', input: [[12, 1, 12], 10], expected: [true, false, true] },
    ],
    hints: ['Compute max(candies) once.', 'Each answer is candies[i] + extraCandies >= current_max.'],
  },
  'can-place-flowers': {
    title: 'Can Place Flowers',
    topic: 'Array / String',
    difficulty: 'Easy',
    statement: 'Given a flowerbed where 1 means planted and 0 means empty, decide whether n new flowers can be planted without adjacent flowers.',
    signature: 'def canPlaceFlowers(flowerbed: List[int], n: int) -> bool',
    functionName: 'canPlaceFlowers',
    starterCode: makeStarter('canPlaceFlowers', 'flowerbed: List[int], n: int', 'Return whether n flowers can be planted.'),
    examples: [
      { input: 'flowerbed = [1,0,0,0,1], n = 1', output: 'True' },
      { input: 'flowerbed = [1,0,0,0,1], n = 2', output: 'False' },
    ],
    constraints: ['You may mutate a local copy or the input.', 'Edges only have one neighbor.'],
    tests: [
      { name: 'one fits', input: [[1, 0, 0, 0, 1], 1], expected: true },
      { name: 'two do not fit', input: [[1, 0, 0, 0, 1], 2], expected: false },
      { name: 'empty single bed', input: [[0], 1], expected: true },
    ],
    hints: ['Check left and right neighbors with boundary guards.', 'Plant greedily when a slot is valid.'],
  },
  'reverse-vowels-of-a-string': {
    title: 'Reverse Vowels of a String',
    topic: 'Array / String',
    difficulty: 'Easy',
    statement: 'Return a string where only the vowels have been reversed. All consonants and positions that are not vowels keep their relative places.',
    signature: 'def reverseVowels(s: str) -> str',
    functionName: 'reverseVowels',
    starterCode: makeStarter('reverseVowels', 's: str', 'Return s with vowels reversed.'),
    examples: [
      { input: 's = "hello"', output: '"holle"' },
      { input: 's = "leetcode"', output: '"leotcede"' },
    ],
    constraints: ['Vowels are a, e, i, o, u in both cases.', 'Return a new string.'],
    tests: [
      { name: 'simple word', input: ['hello'], expected: 'holle' },
      { name: 'multiple vowels', input: ['leetcode'], expected: 'leotcede' },
      { name: 'case-sensitive vowels', input: ['Aa'], expected: 'aA' },
    ],
    hints: ['Use two pointers.', 'Swap only when both pointers are on vowels.'],
  },
  'reverse-words-in-a-string': {
    title: 'Reverse Words in a String',
    topic: 'Array / String',
    difficulty: 'Medium',
    statement: 'Reverse the order of words in a string. Collapse extra spaces so the output has single spaces between words and no leading or trailing spaces.',
    signature: 'def reverseWords(s: str) -> str',
    functionName: 'reverseWords',
    starterCode: makeStarter('reverseWords', 's: str', 'Return words in reverse order.'),
    examples: [
      { input: 's = "the sky is blue"', output: '"blue is sky the"' },
      { input: 's = "  hello world  "', output: '"world hello"' },
    ],
    constraints: ['Words are separated by one or more spaces.', 'Output spacing must be normalized.'],
    tests: [
      { name: 'normal sentence', input: ['the sky is blue'], expected: 'blue is sky the' },
      { name: 'outer spaces', input: ['  hello world  '], expected: 'world hello' },
      { name: 'many internal spaces', input: ['a good   example'], expected: 'example good a' },
    ],
    hints: ['split() without an argument handles repeated whitespace.', 'Reverse the token list, not the characters.'],
  },
  'product-of-array-except-self': {
    title: 'Product of Array Except Self',
    topic: 'Array / String',
    difficulty: 'Medium',
    statement: 'For each index, return the product of every number except the one at that index without using division.',
    signature: 'def productExceptSelf(nums: List[int]) -> List[int]',
    functionName: 'productExceptSelf',
    starterCode: makeStarter('productExceptSelf', 'nums: List[int]', 'Return products excluding each position.'),
    examples: [
      { input: 'nums = [1,2,3,4]', output: '[24,12,8,6]' },
      { input: 'nums = [-1,1,0,-3,3]', output: '[0,0,9,0,0]' },
    ],
    constraints: ['Do not use division.', 'Aim for O(n) time.'],
    tests: [
      { name: 'positive values', input: [[1, 2, 3, 4]], expected: [24, 12, 8, 6] },
      { name: 'contains zero', input: [[-1, 1, 0, -3, 3]], expected: [0, 0, 9, 0, 0] },
      { name: 'two values', input: [[2, 3]], expected: [3, 2] },
    ],
    hints: ['Prefix product from the left and suffix product from the right.', 'The output array can store one pass of products.'],
  },
  'increasing-triplet-subsequence': {
    title: 'Increasing Triplet Subsequence',
    topic: 'Array / String',
    difficulty: 'Medium',
    statement: 'Return true if there exist three indices i < j < k such that nums[i] < nums[j] < nums[k].',
    signature: 'def increasingTriplet(nums: List[int]) -> bool',
    functionName: 'increasingTriplet',
    starterCode: makeStarter('increasingTriplet', 'nums: List[int]', 'Return whether an increasing triplet exists.'),
    examples: [
      { input: 'nums = [1,2,3,4,5]', output: 'True' },
      { input: 'nums = [5,4,3,2,1]', output: 'False' },
    ],
    constraints: ['Use the order of elements.', 'O(n) time is expected.'],
    tests: [
      { name: 'increasing list', input: [[1, 2, 3, 4, 5]], expected: true },
      { name: 'decreasing list', input: [[5, 4, 3, 2, 1]], expected: false },
      { name: 'hidden middle', input: [[2, 1, 5, 0, 4, 6]], expected: true },
    ],
    hints: ['Track the smallest first and second values seen so far.', 'Finding a value larger than both completes the triplet.'],
  },
  'move-zeroes': {
    title: 'Move Zeroes',
    topic: 'Two Pointers',
    difficulty: 'Easy',
    statement: 'Move all zeros to the end while preserving the order of non-zero values. For this Forge judge, return the final list.',
    signature: 'def moveZeroes(nums: List[int]) -> List[int]',
    functionName: 'moveZeroes',
    starterCode: makeStarter('moveZeroes', 'nums: List[int]', 'Return nums after moving zeroes to the end.'),
    examples: [
      { input: 'nums = [0,1,0,3,12]', output: '[1,3,12,0,0]' },
    ],
    constraints: ['Keep non-zero values in their original order.', 'Returning the list is required for this prototype judge.'],
    tests: [
      { name: 'interleaved zeroes', input: [[0, 1, 0, 3, 12]], expected: [1, 3, 12, 0, 0] },
      { name: 'single zero', input: [[0]], expected: [0] },
      { name: 'no zeroes', input: [[1, 2, 3]], expected: [1, 2, 3] },
    ],
    hints: ['Use a write pointer for the next non-zero.', 'Fill remaining positions with zeroes.'],
  },
  'is-subsequence': {
    title: 'Is Subsequence',
    topic: 'Two Pointers',
    difficulty: 'Easy',
    statement: 'Return whether every character in s appears in t in the same order, not necessarily contiguously.',
    signature: 'def isSubsequence(s: str, t: str) -> bool',
    functionName: 'isSubsequence',
    starterCode: makeStarter('isSubsequence', 's: str, t: str', 'Return whether s is a subsequence of t.'),
    examples: [
      { input: 's = "abc", t = "ahbgdc"', output: 'True' },
      { input: 's = "axc", t = "ahbgdc"', output: 'False' },
    ],
    constraints: ['Characters must be matched in order.', 'An empty s is always a subsequence.'],
    tests: [
      { name: 'matches in order', input: ['abc', 'ahbgdc'], expected: true },
      { name: 'missing character', input: ['axc', 'ahbgdc'], expected: false },
      { name: 'empty target subsequence', input: ['', 'anything'], expected: true },
    ],
    hints: ['Advance the s pointer only when characters match.', 'At the end, all of s must have been consumed.'],
  },
  'container-with-most-water': {
    title: 'Container With Most Water',
    topic: 'Two Pointers',
    difficulty: 'Medium',
    statement: 'Choose two vertical lines that form a container with the maximum possible water area.',
    signature: 'def maxArea(height: List[int]) -> int',
    functionName: 'maxArea',
    starterCode: makeStarter('maxArea', 'height: List[int]', 'Return the maximum container area.'),
    examples: [
      { input: 'height = [1,8,6,2,5,4,8,3,7]', output: '49' },
    ],
    constraints: ['Area is width times the shorter height.', 'O(n) two-pointer solution is expected.'],
    tests: [
      { name: 'classic case', input: [[1, 8, 6, 2, 5, 4, 8, 3, 7]], expected: 49 },
      { name: 'two lines', input: [[1, 1]], expected: 1 },
      { name: 'descending-ish', input: [[4, 3, 2, 1, 4]], expected: 16 },
    ],
    hints: ['Start with the widest container.', 'Move the pointer at the shorter line.'],
  },
  'max-number-of-k-sum-pairs': {
    title: 'Max Number of K-Sum Pairs',
    topic: 'Two Pointers',
    difficulty: 'Medium',
    statement: 'Return the maximum number of disjoint pairs whose values sum to k.',
    signature: 'def maxOperations(nums: List[int], k: int) -> int',
    functionName: 'maxOperations',
    starterCode: makeStarter('maxOperations', 'nums: List[int], k: int', 'Return the maximum number of disjoint k-sum pairs.'),
    examples: [
      { input: 'nums = [1,2,3,4], k = 5', output: '2' },
      { input: 'nums = [3,1,3,4,3], k = 6', output: '1' },
    ],
    constraints: ['Each element can be used at most once.', 'Sorting or hash counts are both acceptable.'],
    tests: [
      { name: 'two pairs', input: [[1, 2, 3, 4], 5], expected: 2 },
      { name: 'one pair with duplicates', input: [[3, 1, 3, 4, 3], 6], expected: 1 },
      { name: 'many pairs', input: [[2, 2, 2, 3, 1, 4], 4], expected: 2 },
    ],
    hints: ['Sorted two pointers make pair selection clear.', 'Move both pointers when a pair is formed.'],
  },
  'maximum-average-subarray-i': {
    title: 'Maximum Average Subarray I',
    topic: 'Sliding Window',
    difficulty: 'Easy',
    statement: 'Find the maximum average of any contiguous subarray with exactly k elements.',
    signature: 'def findMaxAverage(nums: List[int], k: int) -> float',
    functionName: 'findMaxAverage',
    starterCode: makeStarter('findMaxAverage', 'nums: List[int], k: int', 'Return the maximum average for a window of size k.'),
    examples: [
      { input: 'nums = [1,12,-5,-6,50,3], k = 4', output: '12.75' },
    ],
    constraints: ['Use exactly k elements.', 'Floating point answers are accepted within a small tolerance.'],
    tests: [
      { name: 'mixed values', input: [[1, 12, -5, -6, 50, 3], 4], expected: 12.75, compare: 'float' },
      { name: 'single value', input: [[5], 1], expected: 5.0, compare: 'float' },
      { name: 'negative values', input: [[-1, -12, -5, -6], 2], expected: -5.5, compare: 'float' },
    ],
    hints: ['Maintain a rolling sum of size k.', 'Update max after each slide.'],
  },
  'maximum-number-of-vowels-in-a-substring': {
    title: 'Maximum Number of Vowels in a Substring',
    topic: 'Sliding Window',
    difficulty: 'Medium',
    statement: 'Return the largest number of vowels found in any substring of length k.',
    signature: 'def maxVowels(s: str, k: int) -> int',
    functionName: 'maxVowels',
    starterCode: makeStarter('maxVowels', 's: str, k: int', 'Return the max vowel count in any length-k window.'),
    examples: [
      { input: 's = "abciiidef", k = 3', output: '3' },
    ],
    constraints: ['Only lowercase English vowels count.', 'Window length must be exactly k.'],
    tests: [
      { name: 'three vowels', input: ['abciiidef', 3], expected: 3 },
      { name: 'all vowels window', input: ['aeiou', 2], expected: 2 },
      { name: 'no vowels', input: ['rhythms', 4], expected: 0 },
    ],
    hints: ['Track entering and leaving characters.', 'A set makes vowel checks constant time.'],
  },
  'max-consecutive-ones-iii': {
    title: 'Max Consecutive Ones III',
    topic: 'Sliding Window',
    difficulty: 'Medium',
    statement: 'Return the longest subarray containing only 1s after flipping at most k zeroes.',
    signature: 'def longestOnes(nums: List[int], k: int) -> int',
    functionName: 'longestOnes',
    starterCode: makeStarter('longestOnes', 'nums: List[int], k: int', 'Return the longest valid window length.'),
    examples: [
      { input: 'nums = [1,1,1,0,0,0,1,1,1,1,0], k = 2', output: '6' },
    ],
    constraints: ['At most k zeroes may be inside the window.', 'Return the window length.'],
    tests: [
      { name: 'classic window', input: [[1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0], 2], expected: 6 },
      { name: 'larger k', input: [[0, 0, 1, 1, 0, 0, 1, 1, 1, 0], 3], expected: 9 },
      { name: 'all ones', input: [[1, 1, 1], 0], expected: 3 },
    ],
    hints: ['Expand right, count zeroes.', 'Shrink left while zeroes exceed k.'],
  },
  'longest-subarray-of-1-s-after-deleting-one-element': {
    title: "Longest Subarray of 1's After Deleting One Element",
    topic: 'Sliding Window',
    difficulty: 'Medium',
    statement: 'Delete exactly one element and return the longest remaining contiguous run of 1s.',
    signature: 'def longestSubarray(nums: List[int]) -> int',
    functionName: 'longestSubarray',
    starterCode: makeStarter('longestSubarray', 'nums: List[int]', 'Return longest 1-run after deleting one element.'),
    examples: [
      { input: 'nums = [1,1,0,1]', output: '3' },
      { input: 'nums = [1,1,1]', output: '2' },
    ],
    constraints: ['Exactly one element must be deleted.', 'A window may contain at most one zero before deletion.'],
    tests: [
      { name: 'bridge one zero', input: [[1, 1, 0, 1]], expected: 3 },
      { name: 'all ones delete one', input: [[1, 1, 1]], expected: 2 },
      { name: 'many zeroes', input: [[0, 1, 1, 1, 0, 1, 1, 0, 1]], expected: 5 },
    ],
    hints: ['Same as at most one zero in the window, then subtract one deleted element.', 'Watch the all-ones case.'],
  },
  'find-the-highest-altitude': {
    title: 'Find the Highest Altitude',
    topic: 'Prefix Sum',
    difficulty: 'Easy',
    statement: 'Starting at altitude 0, apply each gain value and return the highest altitude reached.',
    signature: 'def largestAltitude(gain: List[int]) -> int',
    functionName: 'largestAltitude',
    starterCode: makeStarter('largestAltitude', 'gain: List[int]', 'Return the maximum running altitude.'),
    examples: [
      { input: 'gain = [-5,1,5,0,-7]', output: '1' },
    ],
    constraints: ['Initial altitude is 0.', 'Include the initial altitude when computing the maximum.'],
    tests: [
      { name: 'goes above start', input: [[-5, 1, 5, 0, -7]], expected: 1 },
      { name: 'always up', input: [[4, -1, 2, -3]], expected: 5 },
      { name: 'never above zero', input: [[-4, -3, -2, -1, 4, 3, 2]], expected: 0 },
    ],
    hints: ['Keep a running altitude.', 'Update the answer after applying each gain.'],
  },
  'find-pivot-index': {
    title: 'Find Pivot Index',
    topic: 'Prefix Sum',
    difficulty: 'Easy',
    statement: 'Return the leftmost index where the sum of values to the left equals the sum of values to the right. Return -1 if none exists.',
    signature: 'def pivotIndex(nums: List[int]) -> int',
    functionName: 'pivotIndex',
    starterCode: makeStarter('pivotIndex', 'nums: List[int]', 'Return the leftmost pivot index, or -1.'),
    examples: [
      { input: 'nums = [1,7,3,6,5,6]', output: '3' },
      { input: 'nums = [1,2,3]', output: '-1' },
    ],
    constraints: ['The pivot value itself is not included in either side.', 'Return the first valid index.'],
    tests: [
      { name: 'middle pivot', input: [[1, 7, 3, 6, 5, 6]], expected: 3 },
      { name: 'no pivot', input: [[1, 2, 3]], expected: -1 },
      { name: 'leftmost pivot', input: [[2, 1, -1]], expected: 0 },
    ],
    hints: ['Let total be the full sum.', 'At index i, right sum is total - left - nums[i].'],
  },
  'find-the-difference-of-two-arrays': {
    title: 'Find the Difference of Two Arrays',
    topic: 'Hash Map / Set',
    difficulty: 'Easy',
    statement: 'Return two lists: values present in nums1 but not nums2, and values present in nums2 but not nums1. Order does not matter.',
    signature: 'def findDifference(nums1: List[int], nums2: List[int]) -> List[List[int]]',
    functionName: 'findDifference',
    starterCode: makeStarter('findDifference', 'nums1: List[int], nums2: List[int]', 'Return two distinct-value difference lists.'),
    examples: [
      { input: 'nums1 = [1,2,3], nums2 = [2,4,6]', output: '[[1,3],[4,6]]' },
    ],
    constraints: ['Each returned value should appear once.', 'Order inside each returned list is ignored by the Forge judge.'],
    tests: [
      { name: 'two differences', input: [[1, 2, 3], [2, 4, 6]], expected: [[1, 3], [4, 6]], compare: 'sortNested' },
      { name: 'duplicates ignored', input: [[1, 2, 3, 3], [1, 1, 2, 2]], expected: [[3], []], compare: 'sortNested' },
      { name: 'negative values', input: [[-1, 0, 1], [0, 2]], expected: [[-1, 1], [2]], compare: 'sortNested' },
    ],
    hints: ['Convert both inputs to sets.', 'Return set differences, not per-element duplicate differences.'],
  },
  'unique-number-of-occurrences': {
    title: 'Unique Number of Occurrences',
    topic: 'Hash Map / Set',
    difficulty: 'Easy',
    statement: 'Return whether every distinct value in the array has a unique occurrence count.',
    signature: 'def uniqueOccurrences(arr: List[int]) -> bool',
    functionName: 'uniqueOccurrences',
    starterCode: makeStarter('uniqueOccurrences', 'arr: List[int]', 'Return whether all frequencies are unique.'),
    examples: [
      { input: 'arr = [1,2,2,1,1,3]', output: 'True' },
      { input: 'arr = [1,2]', output: 'False' },
    ],
    constraints: ['Count each distinct integer.', 'No two values may have the same frequency.'],
    tests: [
      { name: 'unique counts', input: [[1, 2, 2, 1, 1, 3]], expected: true },
      { name: 'duplicate counts', input: [[1, 2]], expected: false },
      { name: 'negative values', input: [[-3, 0, 1, -3, 1, 1, 1, -3, 10, 0]], expected: true },
    ],
    hints: ['Use Counter or a dictionary.', 'Compare number of counts to number of unique counts.'],
  },
}

export function getCodingProblemDetail(problem: ProblemTuple, index: number): CodingProblemDetail {
  const [topic, title, difficulty, source] = problem
  const slug = slugify(title)
  const defined = definedProblems[slug]

  if (defined) {
    return {
      ...defined,
      slug,
      source,
      judgeReady: true,
    }
  }

  return {
    slug,
    title,
    topic,
    difficulty,
    source,
    statement: `Forge has loaded ${title} as a ${topic} practice mission. Write a Python function that solves the problem, explain the invariant, and validate edge cases before submitting.`,
    signature: 'def solve(*args)',
    functionName: 'solve',
    starterCode: makeStarter('solve', '*args', `Prototype solution for ${title}.`),
    examples: [
      { input: 'Use the examples from the mission brief.', output: 'Return the value requested by the prompt.' },
    ],
    constraints: ['This problem detail is loaded.', 'The executable judge for this row is not configured yet.', `Question #${index + 1} in Forge 75.`],
    tests: [],
    hints: [patternPlaybookFallback(topic), 'Use the detail panel to mark solved or send to review after practicing.'],
    judgeReady: false,
  }
}

export function getCodingProblemBySlug(slug: string): CodingProblemDetail | null {
  const defined = definedProblems[slug]
  if (!defined) return null

  return {
    ...defined,
    slug,
    source: 'LC75',
    judgeReady: true,
  }
}

function patternPlaybookFallback(topic: string) {
  const fallbacks: Record<string, string> = {
    'Array / String': 'Start by naming the transformation and the edge cases around empty inputs.',
    'Two Pointers': 'Define what each pointer means and why it moves.',
    'Sliding Window': 'Define what makes the current window valid.',
    'Prefix Sum': 'Use running totals to avoid repeated summation.',
    'Hash Map / Set': 'Define what each key and value means.',
    Stack: 'Maintain an invariant for unresolved elements.',
    Queue: 'Model order and expiration directly.',
    'Linked List': 'Draw pointer movement before mutating links.',
    'Dynamic Programming': 'State the subproblem and transition.',
  }

  return fallbacks[topic] ?? 'State the invariant, complexity, and failure cases before coding.'
}
