#!/usr/bin/env node

/**
 * Test script for OPML generation
 * This script simulates the Netlify function environment locally
 */

const fs = require('fs');
const path = require('path');
const { handler } = require('./functions/generate-opml');

// Mock the Netlify function environment
process.env.URL = 'http://localhost:8888';

// Test cases
const testCases = [
    {
        name: 'Test with valid comics',
        body: {
            comics: ['garfield', 'calvinandhobbes', 'peanuts']
        }
    },
    {
        name: 'Test with non-existent comics',
        body: {
            comics: ['non-existent-comic-1', 'non-existent-comic-2']
        }
    },
    {
        name: 'Test with mixed valid and invalid comics',
        body: {
            comics: ['garfield', 'non-existent-comic', 'peanuts']
        }
    },
    {
        name: 'Test with empty selection',
        body: {
            comics: []
        }
    }
];

// Run tests
async function runTests() {
    console.log('Starting OPML generation tests...\n');
    
    for (const testCase of testCases) {
        console.log(`Running test: ${testCase.name}`);
        console.log('Request body:', JSON.stringify(testCase.body, null, 2));
        
        try {
            // Create a mock event object
            const event = {
                httpMethod: 'POST',
                body: JSON.stringify(testCase.body)
            };
            
            // Call the handler function
            const response = await handler(event, {});
            
            console.log('Response status:', response.statusCode);
            console.log('Response headers:', response.headers);
            
            if (response.statusCode === 200) {
                console.log('OPML content:');
                console.log(response.body);
                
                // Save OPML to file for inspection
                const outputPath = path.join('test_functions', `${testCase.name.toLowerCase().replace(/\s+/g, '_')}.opml`);
                fs.writeFileSync(outputPath, response.body);
                console.log(`Saved OPML to: ${outputPath}`);
            } else {
                console.log('Error response:', response.body);
            }
        } catch (error) {
            console.error('Test failed with error:', error);
        }
        
        console.log('\n' + '-'.repeat(80) + '\n');
    }
    
    console.log('Tests completed!');
}

// Run the tests
runTests().catch(error => {
    console.error('Test script failed:', error);
    process.exit(1);
}); 